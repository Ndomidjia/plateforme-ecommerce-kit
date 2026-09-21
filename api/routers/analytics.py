"""Endpoints de lecture sur les résultats des modules ML (schéma analytics).

Accessibles aux deux rôles (admin et analyst) : ce sont des données déjà
agrégées/anonymisées au niveau segment ou produit, pas des données
personnelles brutes (celles-ci sont derrière les endpoints RGPD, protégés
plus strictement).
"""
import statistics
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection

from database import get_db
from deps import require_role

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_role("admin", "analyst"))])

def _customer_360_reliability(db: Connection) -> tuple[float, str]:
    """Lit l'AUC hors échantillon (oof_roc_auc) de la version ACTIVE (promue)
    de analytics/customer_360_olist.py, via analytics.model_registry, plutôt
    qu'une valeur codée en dur ou que la dernière ligne de
    model_metrics_history — cette dernière peut désormais contenir un run
    REJETÉ (non promu, voir analytics/model_registry.py), dont la métrique ne
    correspondrait plus aux données réellement servies par
    analytics.customer_360. Voir docs/limitations-methodologiques.md pour
    l'interprétation."""
    auc = db.execute(
        text("SELECT active_metric FROM analytics.model_registry WHERE model_name = 'customer_360_proxy'")
    ).scalar()
    if auc is None:
        return 0.5, "Module jamais exécuté : aucune métrique de fiabilité disponible."
    auc = float(auc)
    verdict = "quasi nul" if auc < 0.65 else ("limité" if auc < 0.75 else "correct")
    note = (
        f"AUC = {auc:.2f} (0.50 = hasard) : ce modèle a un pouvoir prédictif {verdict} avec les "
        "seules données de la 1re commande. À considérer comme exploratoire, pas comme un "
        "outil de ciblage marketing fiable. Voir docs/limitations-methodologiques.md."
    )
    return auc, note

class OverviewKPIs(BaseModel):
    olist_customers: int
    retailrocket_visitors: int
    churn_customers: int
    churn_avg_proba: Optional[float]
    churn_pct_high_risk: Optional[float]
    rfm_dominant_segment: Optional[str]
    rfm_dominant_segment_count: int
    funnel_global_conversion_rate: Optional[float]
    association_rules_significant_count: int
    total_value_at_risk: float
    recommendation_catalog_coverage_pct: float
    funnel_trend_delta_pct: Optional[float]
    pct_negative_reviews: Optional[float]

class FeatureImportance(BaseModel):
    feature: str
    importance: float

class ReturnsByRisk(BaseModel):
    risk_level: str
    avg_returns_rate: float

class GeoDistribution(BaseModel):
    customer_state: str
    customer_count: int

class RetentionEstimate(BaseModel):
    targeted_customers: int
    avg_churn_proba_targeted: float
    total_ltv_targeted: float
    estimated_value_saved: float

class DeliveryKPI(BaseModel):
    avg_delivery_days: float
    avg_delay_vs_estimate_days: float
    pct_late_deliveries: float

class SentimentTrend(BaseModel):
    period: str
    pct_negative: float
    avg_review_score: float

class TopItem(BaseModel):
    item_id: int
    views: int
    addtocarts: int

class PaymentMethod(BaseModel):
    payment_type: str
    count: int
    avg_value: float
    total_value: float

class MarketingAction(BaseModel):
    customer_id: int
    churn_proba: float
    risk_level: str
    primary_risk_factor: str
    recommended_action: str

class Anomaly(BaseModel):
    metric: str
    period: str
    value: float
    expected_value: float
    z_score: float
    severity: str  # warning | critical

# --- Recommandation d'action marketing ---
# Pour chaque variable comportementale connue pour peser sur le churn (voir
# analytics.churn_feature_importance), on associe une direction "à risque"
# (valeur haute ou basse) et une action marketing concrète. Le facteur retenu
# pour un client donné est celui où il s'écarte le plus de la moyenne de la
# population (z-score), pondéré par l'importance globale de la variable dans
# le modèle -- pas un diagnostic causal, une heuristique d'aide à la décision.
ACTION_RULES = [
    {"feature": "customer_service_calls", "direction": "high",
     "reason": "Nombreux appels au support client", "action": "Contact proactif prioritaire par un conseiller dédié"},
    {"feature": "cart_abandonment_rate", "direction": "high",
     "reason": "Fort taux d'abandon de panier", "action": "Email de relance panier avec incitation (livraison offerte, réduction ciblée)"},
    {"feature": "days_since_last_purchase", "direction": "high",
     "reason": "Inactif depuis longtemps", "action": "Campagne de réactivation (offre de bienvenue retour)"},
    {"feature": "discount_usage_rate", "direction": "high",
     "reason": "Très sensible aux promotions", "action": "Offre de réduction personnalisée pour réengagement"},
    {"feature": "email_open_rate", "direction": "low",
     "reason": "Faible engagement par email", "action": "Basculer vers un autre canal (SMS, notification app)"},
    {"feature": "returns_rate", "direction": "high",
     "reason": "Taux de retour produit élevé", "action": "Vérifier l'adéquation catalogue / qualité produit livré"},
    {"feature": "lifetime_value", "direction": "high",
     "reason": "Client à forte valeur en risque de départ", "action": "Contact commercial dédié / programme VIP de rétention"},
    {"feature": "social_media_engagement_score", "direction": "low",
     "reason": "Faible engagement sur les réseaux sociaux", "action": "Campagne de réengagement communautaire / contenu personnalisé"},
]

def _load_feature_importance(db: Connection) -> dict:
    rows = db.execute(
        text("SELECT feature, importance FROM analytics.churn_feature_importance "
             "WHERE model_version = (SELECT model_version FROM analytics.churn_feature_importance "
             "ORDER BY computed_at DESC LIMIT 1)")
    ).mappings().all()
    return {r["feature"].replace("num__", "").replace("cat__", ""): r["importance"] for r in rows}

def _load_feature_stats(db: Connection) -> dict:
    cols = ", ".join(f"AVG({r['feature']}) AS {r['feature']}_mean, STDDEV({r['feature']}) AS {r['feature']}_std"
                      for r in ACTION_RULES)
    row = db.execute(text(f"SELECT {cols} FROM churn.customer_profiles")).mappings().first()
    return dict(row)

def _pick_primary_factor(customer: dict, stats: dict, importance: dict) -> tuple[str, str]:
    best_score, best_rule = 0.0, None
    for rule in ACTION_RULES:
        feature = rule["feature"]
        value = customer[feature]
        mean, std = stats[f"{feature}_mean"], stats[f"{feature}_std"]
        if value is None or mean is None or not std:
            continue
        z = (value - mean) / std if rule["direction"] == "high" else (mean - value) / std
        weighted = z * importance.get(feature, 0.05)
        if weighted > best_score:
            best_score, best_rule = weighted, rule
    if best_rule is None:
        return "Profil atypique, pas de facteur dominant identifié", "Analyse individuelle recommandée"
    return best_rule["reason"], best_rule["action"]

class RFMSegment(BaseModel):
    customer_unique_id: str
    recency_days: int
    frequency: int
    monetary: float
    r_score: int
    f_score: int
    m_score: int
    segment: str

class ChurnScore(BaseModel):
    customer_id: int
    churn_proba: float
    risk_level: str
    model_version: str

class ChurnSummary(BaseModel):
    risk_level: str
    count: int
    avg_churn_proba: float

class FunnelStat(BaseModel):
    period_start: str
    period_end: str
    views: int
    addtocarts: int
    transactions: int
    view_to_cart_rate: Optional[float]
    cart_to_buy_rate: Optional[float]

class ItemRecommendation(BaseModel):
    recommended_item_id: int
    score: float
    method: str

class AssociationRule(BaseModel):
    antecedents: str
    consequents: str
    support: float
    confidence: float
    lift: float

class RFMSegmentSummary(BaseModel):
    segment: str
    count: int
    avg_monetary: float

class SentimentSummary(BaseModel):
    sentiment: str
    count: int
    avg_review_score: float

class ReviewSentiment(BaseModel):
    review_id: str
    order_id: str
    review_score: int
    sentiment: str
    sentiment_proba: float

@router.get("/overview", response_model=OverviewKPIs)
def get_overview(db: Connection = Depends(get_db)):
    """KPIs agrégés, un par module, pour la page d'accueil du dashboard."""
    olist_customers = db.execute(
        text("SELECT COUNT(DISTINCT customer_unique_id) FROM olist.customers")
    ).scalar()
    retailrocket_visitors = db.execute(
        text("SELECT COUNT(DISTINCT visitor_id) FROM retailrocket.events")
    ).scalar()
    churn_customers = db.execute(text("SELECT COUNT(*) FROM churn.customer_profiles")).scalar()

    churn_row = db.execute(
        text("SELECT AVG(churn_proba) AS avg_proba, "
             "AVG((risk_level = 'high')::int) AS pct_high FROM analytics.churn_scores")
    ).mappings().first()

    # `.first()` sur un GROUP BY / ORDER BY ... LIMIT 1 renvoie None (zéro
    # ligne), pas une ligne de NULL, quand la table source est vide (avant le
    # premier calcul du module -- ex. juste après `docker compose up`, ou en
    # CI sur un schéma sans données, voir tests/test_data_quality.py) :
    # contrairement à un agrégat simple (AVG/SUM) qui renvoie toujours une
    # ligne. Sans ce garde-fou, la page d'accueil du dashboard renvoyait une
    # 500 tant qu'aucun module n'avait encore tourné.
    rfm_row = db.execute(
        text("SELECT segment, COUNT(*) AS count FROM analytics.rfm_segments "
             "GROUP BY segment ORDER BY count DESC LIMIT 1")
    ).mappings().first() or {"segment": None, "count": 0}

    # La ligne "globale" du funnel est celle qui couvre la plus longue période
    # (les autres sont des découpages hebdomadaires) — voir funnel_retailrocket.py.
    funnel_row = db.execute(
        text("SELECT view_to_cart_rate * cart_to_buy_rate AS conversion_rate "
             "FROM analytics.funnel_stats ORDER BY (period_end - period_start) DESC LIMIT 1")
    ).mappings().first() or {"conversion_rate": None}

    rules_count = db.execute(
        text("SELECT COUNT(*) FROM analytics.association_rules WHERE lift >= 1")
    ).scalar()

    value_at_risk = db.execute(
        text("SELECT COALESCE(SUM(cp.lifetime_value), 0) FROM analytics.churn_scores cs "
             "JOIN churn.customer_profiles cp ON cp.customer_id = cs.customer_id "
             "WHERE cs.risk_level = 'high'")
    ).scalar()

    catalog_coverage = db.execute(
        text("SELECT (SELECT COUNT(DISTINCT item_id) FROM analytics.item_recommendations)::float "
             "/ NULLIF((SELECT COUNT(DISTINCT item_id) FROM retailrocket.events), 0)")
    ).scalar()

    # Tendance : delta entre les deux dernières semaines complètes (on exclut
    # la ligne "globale", repérable à sa période bien plus longue qu'une semaine).
    last_two_weeks = db.execute(
        text("SELECT view_to_cart_rate * cart_to_buy_rate AS conversion_rate "
             "FROM analytics.funnel_stats WHERE (period_end - period_start) < 30 "
             "ORDER BY period_start DESC LIMIT 2")
    ).scalars().all()
    trend_delta = None
    if len(last_two_weeks) == 2 and last_two_weeks[1]:
        trend_delta = (last_two_weeks[0] - last_two_weeks[1]) / last_two_weeks[1]

    pct_negative = db.execute(
        text("SELECT AVG((sentiment = 'negative')::int) FROM analytics.review_sentiment")
    ).scalar()

    return OverviewKPIs(
        olist_customers=olist_customers,
        retailrocket_visitors=retailrocket_visitors,
        churn_customers=churn_customers,
        churn_avg_proba=churn_row["avg_proba"],
        churn_pct_high_risk=churn_row["pct_high"],
        rfm_dominant_segment=rfm_row["segment"],
        rfm_dominant_segment_count=rfm_row["count"],
        funnel_global_conversion_rate=funnel_row["conversion_rate"],
        association_rules_significant_count=rules_count,
        total_value_at_risk=value_at_risk,
        recommendation_catalog_coverage_pct=catalog_coverage or 0,
        funnel_trend_delta_pct=trend_delta,
        pct_negative_reviews=pct_negative,
    )

@router.get("/churn/feature-importance", response_model=list[FeatureImportance])
def get_churn_feature_importance(limit: int = Query(15, le=50), db: Connection = Depends(get_db)):
    # Déclaré AVANT /churn/{customer_id} (même raison que /churn/summary).
    rows = db.execute(
        text("SELECT feature, importance FROM analytics.churn_feature_importance "
             "WHERE model_version = (SELECT model_version FROM analytics.churn_feature_importance "
             "ORDER BY computed_at DESC LIMIT 1) "
             "ORDER BY importance DESC LIMIT :limit"),
        {"limit": limit},
    ).mappings().all()
    return rows

@router.get("/churn/returns-by-risk", response_model=list[ReturnsByRisk])
def get_returns_by_risk(db: Connection = Depends(get_db)):
    # Déclaré AVANT /churn/{customer_id} (même raison que /churn/summary).
    rows = db.execute(
        text("SELECT cs.risk_level, AVG(cp.returns_rate) AS avg_returns_rate "
             "FROM analytics.churn_scores cs "
             "JOIN churn.customer_profiles cp ON cp.customer_id = cs.customer_id "
             "WHERE cp.returns_rate IS NOT NULL "
             "GROUP BY cs.risk_level ORDER BY avg_returns_rate DESC")
    ).mappings().all()
    return rows

@router.get("/olist/geo-distribution", response_model=list[GeoDistribution])
def get_geo_distribution(db: Connection = Depends(get_db)):
    rows = db.execute(
        text("SELECT customer_state, COUNT(DISTINCT customer_unique_id) AS customer_count "
             "FROM olist.customers WHERE customer_state IS NOT NULL "
             "GROUP BY customer_state ORDER BY customer_count DESC")
    ).mappings().all()
    return rows

@router.get("/rfm/summary", response_model=list[RFMSegmentSummary])
def get_rfm_summary(db: Connection = Depends(get_db)):
    # Déclaré AVANT /rfm/{customer_unique_id} (même raison que /churn/summary).
    rows = db.execute(
        text("SELECT segment, COUNT(*) AS count, AVG(monetary) AS avg_monetary "
             "FROM analytics.rfm_segments GROUP BY segment ORDER BY count DESC")
    ).mappings().all()
    return rows

@router.get("/rfm/{customer_unique_id}", response_model=RFMSegment)
def get_rfm_segment(customer_unique_id: str, db: Connection = Depends(get_db)):
    row = db.execute(
        text("SELECT customer_unique_id, recency_days, frequency, monetary, "
             "r_score, f_score, m_score, segment FROM analytics.rfm_segments "
             "WHERE customer_unique_id = :cid"),
        {"cid": customer_unique_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Client inconnu dans analytics.rfm_segments")
    return row

@router.get("/rfm", response_model=list[RFMSegment])
def list_rfm_segments(
    segment: Optional[str] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Connection = Depends(get_db),
):
    query = ("SELECT customer_unique_id, recency_days, frequency, monetary, "
             "r_score, f_score, m_score, segment FROM analytics.rfm_segments")
    params = {"limit": limit, "offset": offset}
    if segment:
        query += " WHERE segment = :segment"
        params["segment"] = segment
    query += " ORDER BY customer_unique_id LIMIT :limit OFFSET :offset"
    rows = db.execute(text(query), params).mappings().all()
    return rows

@router.get("/churn/summary", response_model=list[ChurnSummary])
def get_churn_summary(db: Connection = Depends(get_db)):
    # Déclaré AVANT /churn/{customer_id} : FastAPI fait correspondre les
    # routes dans l'ordre de déclaration, "summary" serait sinon interprété
    # comme une tentative de customer_id (échec de conversion en int -> 422).
    rows = db.execute(
        text("SELECT risk_level, COUNT(*) AS count, AVG(churn_proba) AS avg_churn_proba "
             "FROM analytics.churn_scores GROUP BY risk_level ORDER BY avg_churn_proba")
    ).mappings().all()
    return rows

@router.get("/churn/retention-estimate", response_model=RetentionEstimate)
def get_retention_estimate(
    top_n: int = Query(500, ge=1, le=50000, description="Nombre de clients les plus à risque à cibler"),
    success_rate: float = Query(0.3, ge=0.0, le=1.0, description="Taux de succès supposé de la campagne de rétention"),
    db: Connection = Depends(get_db),
):
    """Calculateur d'aide à la décision : si on cible les N clients les plus
    à risque de churn avec une campagne de rétention, et qu'elle réussit avec
    la probabilité success_rate, quelle valeur (LTV) espère-t-on sauver ?
    Estimation simple (LTV moyenne x taux de succès), pas un modèle causal :
    à présenter comme un ordre de grandeur, pas une prédiction garantie.
    """
    row = db.execute(
        text("""
            SELECT COUNT(*) AS n, AVG(top.churn_proba) AS avg_proba, SUM(cp.lifetime_value) AS total_ltv
            FROM (
                SELECT customer_id, churn_proba FROM analytics.churn_scores
                ORDER BY churn_proba DESC LIMIT :top_n
            ) top
            JOIN churn.customer_profiles cp ON cp.customer_id = top.customer_id
        """),
        {"top_n": top_n},
    ).mappings().first()
    total_ltv = float(row["total_ltv"] or 0)
    return RetentionEstimate(
        targeted_customers=row["n"],
        avg_churn_proba_targeted=float(row["avg_proba"] or 0),
        total_ltv_targeted=total_ltv,
        estimated_value_saved=total_ltv * success_rate,
    )

@router.get("/olist/delivery", response_model=DeliveryKPI)
def get_delivery_kpi(db: Connection = Depends(get_db)):
    row = db.execute(
        text("""
            SELECT
                AVG(EXTRACT(EPOCH FROM (order_delivered_customer_date - order_purchase_timestamp)) / 86400) AS avg_delivery_days,
                AVG(EXTRACT(EPOCH FROM (order_delivered_customer_date - order_estimated_delivery_date)) / 86400) AS avg_delay,
                AVG((order_delivered_customer_date > order_estimated_delivery_date)::int) AS pct_late
            FROM olist.orders
            WHERE order_delivered_customer_date IS NOT NULL AND order_estimated_delivery_date IS NOT NULL
        """)
    ).mappings().first()
    return DeliveryKPI(
        avg_delivery_days=row["avg_delivery_days"] or 0,
        avg_delay_vs_estimate_days=row["avg_delay"] or 0,
        pct_late_deliveries=row["pct_late"] or 0,
    )

@router.get("/sentiment/trend", response_model=list[SentimentTrend])
def get_sentiment_trend(db: Connection = Depends(get_db)):
    # Déclaré AVANT toute route /sentiment/{...} si elle existait un jour.
    rows = db.execute(
        text("""
            SELECT to_char(date_trunc('month', r.review_creation_date), 'YYYY-MM') AS period,
                   AVG((s.sentiment = 'negative')::int) AS pct_negative,
                   AVG(s.review_score) AS avg_review_score
            FROM analytics.review_sentiment s
            JOIN olist.order_reviews r ON r.review_id = s.review_id AND r.order_id = s.order_id
            GROUP BY period ORDER BY period
        """)
    ).mappings().all()
    return rows

@router.get("/retailrocket/top-items", response_model=list[TopItem])
def get_top_items(limit: int = Query(10, le=50), db: Connection = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT item_id,
                   COUNT(*) FILTER (WHERE event_type = 'view') AS views,
                   COUNT(*) FILTER (WHERE event_type = 'addtocart') AS addtocarts
            FROM retailrocket.events
            GROUP BY item_id
            ORDER BY views DESC
            LIMIT :limit
        """),
        {"limit": limit},
    ).mappings().all()
    return rows

@router.get("/olist/payment-methods", response_model=list[PaymentMethod])
def get_payment_methods(db: Connection = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT payment_type, COUNT(*) AS count,
                   AVG(payment_value) AS avg_value, SUM(payment_value) AS total_value
            FROM olist.order_payments
            GROUP BY payment_type ORDER BY count DESC
        """)
    ).mappings().all()
    return rows

@router.get("/churn/marketing-actions", response_model=list[MarketingAction])
def get_marketing_actions(
    risk_level: str = Query("high", description="Niveau de risque ciblé"),
    limit: int = Query(20, le=200),
    db: Connection = Depends(get_db),
):
    feature_cols = ", ".join(r["feature"] for r in ACTION_RULES)
    rows = db.execute(
        text(f"""
            SELECT cp.customer_id, {feature_cols}, cs.churn_proba, cs.risk_level
            FROM analytics.churn_scores cs
            JOIN churn.customer_profiles cp ON cp.customer_id = cs.customer_id
            WHERE cs.risk_level = :risk_level
            ORDER BY cs.churn_proba DESC
            LIMIT :limit
        """),
        {"risk_level": risk_level, "limit": limit},
    ).mappings().all()

    stats = _load_feature_stats(db)
    importance = _load_feature_importance(db)

    results = []
    for row in rows:
        reason, action = _pick_primary_factor(row, stats, importance)
        results.append(MarketingAction(
            customer_id=row["customer_id"],
            churn_proba=row["churn_proba"],
            risk_level=row["risk_level"],
            primary_risk_factor=reason,
            recommended_action=action,
        ))
    return results

@router.get("/churn/{customer_id}", response_model=ChurnScore)
def get_churn_score(customer_id: int, db: Connection = Depends(get_db)):
    row = db.execute(
        text("SELECT customer_id, churn_proba, risk_level, model_version "
             "FROM analytics.churn_scores WHERE customer_id = :cid"),
        {"cid": customer_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Client inconnu dans analytics.churn_scores")
    return row

@router.get("/churn", response_model=list[ChurnScore])
def list_churn_scores(
    risk_level: Optional[str] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Connection = Depends(get_db),
):
    query = "SELECT customer_id, churn_proba, risk_level, model_version FROM analytics.churn_scores"
    params = {"limit": limit, "offset": offset}
    if risk_level:
        query += " WHERE risk_level = :risk_level"
        params["risk_level"] = risk_level
    query += " ORDER BY churn_proba DESC LIMIT :limit OFFSET :offset"
    rows = db.execute(text(query), params).mappings().all()
    return rows

@router.get("/funnel", response_model=list[FunnelStat])
def get_funnel_stats(db: Connection = Depends(get_db)):
    rows = db.execute(
        text("SELECT period_start::text, period_end::text, views, addtocarts, transactions, "
             "view_to_cart_rate, cart_to_buy_rate FROM analytics.funnel_stats "
             "ORDER BY period_start")
    ).mappings().all()
    return rows

@router.get("/recommendations/{item_id}", response_model=list[ItemRecommendation])
def get_item_recommendations(item_id: int, limit: int = Query(10, le=50), db: Connection = Depends(get_db)):
    rows = db.execute(
        text("SELECT recommended_item_id, score, method FROM analytics.item_recommendations "
             "WHERE item_id = :item_id ORDER BY score DESC LIMIT :limit"),
        {"item_id": item_id, "limit": limit},
    ).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="Aucune recommandation pour ce produit")
    return rows

@router.get("/association-rules", response_model=list[AssociationRule])
def list_association_rules(
    min_lift: Optional[float] = None,
    limit: int = Query(50, le=500),
    db: Connection = Depends(get_db),
):
    query = "SELECT antecedents, consequents, support, confidence, lift FROM analytics.association_rules"
    params = {"limit": limit}
    if min_lift is not None:
        query += " WHERE lift >= :min_lift"
        params["min_lift"] = min_lift
    query += " ORDER BY lift DESC LIMIT :limit"
    rows = db.execute(text(query), params).mappings().all()
    return rows

@router.get("/sentiment/summary", response_model=list[SentimentSummary])
def get_sentiment_summary(db: Connection = Depends(get_db)):
    # Déclaré AVANT /sentiment (même raison que /churn/summary).
    rows = db.execute(
        text("SELECT sentiment, COUNT(*) AS count, AVG(review_score) AS avg_review_score "
             "FROM analytics.review_sentiment GROUP BY sentiment ORDER BY count DESC")
    ).mappings().all()
    return rows

@router.get("/sentiment", response_model=list[ReviewSentiment])
def list_sentiment(
    sentiment: Optional[str] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Connection = Depends(get_db),
):
    query = ("SELECT review_id, order_id, review_score, sentiment, sentiment_proba "
             "FROM analytics.review_sentiment")
    params = {"limit": limit, "offset": offset}
    if sentiment:
        query += " WHERE sentiment = :sentiment"
        params["sentiment"] = sentiment
    query += " ORDER BY sentiment_proba DESC LIMIT :limit OFFSET :offset"
    rows = db.execute(text(query), params).mappings().all()
    return rows

def _detect_anomaly(metric: str, period: str, history: list[float], latest: float) -> Optional[Anomaly]:
    """Écart-type de la période la plus récente par rapport aux périodes
    précédentes (z-score). |z| >= 2 : anomalie statistique (~5% de chances
    d'occurrence sous hypothèse de normalité) ; >= 3 : sévère. Détection
    simple et explicable, pas un modèle de séries temporelles complet."""
    if len(history) < 3:
        return None
    mean = statistics.mean(history)
    stdev = statistics.pstdev(history)
    if stdev == 0:
        return None
    z = (latest - mean) / stdev
    if abs(z) < 2:
        return None
    return Anomaly(
        metric=metric, period=period, value=latest, expected_value=mean,
        z_score=z, severity="critical" if abs(z) >= 3 else "warning",
    )

@router.get("/anomalies", response_model=list[Anomaly])
def get_anomalies(db: Connection = Depends(get_db)):
    anomalies = []

    funnel_rows = db.execute(
        text("SELECT period_start::text, view_to_cart_rate * cart_to_buy_rate AS rate "
             "FROM analytics.funnel_stats WHERE (period_end - period_start) < 30 "
             "ORDER BY period_start")
    ).mappings().all()
    if len(funnel_rows) >= 4:
        history = [r["rate"] for r in funnel_rows[:-1]]
        latest = funnel_rows[-1]
        a = _detect_anomaly("Taux de conversion funnel", latest["period_start"], history, latest["rate"])
        if a:
            anomalies.append(a)

    sentiment_rows = db.execute(
        text("""
            SELECT period, pct_negative FROM (
                SELECT to_char(date_trunc('month', r.review_creation_date), 'YYYY-MM') AS period,
                       AVG((s.sentiment = 'negative')::int) AS pct_negative
                FROM analytics.review_sentiment s
                JOIN olist.order_reviews r ON r.review_id = s.review_id AND r.order_id = s.order_id
                GROUP BY period ORDER BY period
            ) t
        """)
    ).mappings().all()
    if len(sentiment_rows) >= 4:
        history = [r["pct_negative"] for r in sentiment_rows[:-1]]
        latest = sentiment_rows[-1]
        a = _detect_anomaly("Taux d'avis négatifs", latest["period"], history, latest["pct_negative"])
        if a:
            anomalies.append(a)

    return anomalies

# --- Vue client 360° (fusion RFM + proxy de risque + sentiment + reco, sur Olist) ---

class RiskLevelCount(BaseModel):
    risk_level: str
    count: int

class Customer360Summary(BaseModel):
    total_customers: int
    evaluated_customers: int
    censored_customers: int
    repurchase_threshold_days: int
    risk_distribution: list[RiskLevelCount]
    model_auc: float
    model_reliability_note: str

class Customer360(BaseModel):
    customer_unique_id: str
    rfm_segment: Optional[str]
    recency_days: Optional[int]
    frequency: Optional[int]
    monetary: Optional[float]
    is_censored: bool
    proxy_risk_proba: Optional[float]
    proxy_risk_level: Optional[str]
    avg_review_score: Optional[float]
    dominant_sentiment: Optional[str]
    top_category: Optional[str]
    recommended_category: Optional[str]
    recommended_category_lift: Optional[float]

@router.get("/customer-360/summary", response_model=Customer360Summary)
def get_customer_360_summary(db: Connection = Depends(get_db)):
    # Déclaré AVANT /customer-360/{customer_unique_id} (même raison que /churn/summary).
    totals = db.execute(
        text("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE is_censored) AS censored, "
             "MAX(repurchase_threshold_days) AS threshold FROM analytics.customer_360")
    ).mappings().first()
    dist = db.execute(
        text("SELECT proxy_risk_level AS risk_level, COUNT(*) AS count FROM analytics.customer_360 "
             "WHERE NOT is_censored GROUP BY proxy_risk_level")
    ).mappings().all()
    auc, note = _customer_360_reliability(db)
    return Customer360Summary(
        total_customers=totals["total"],
        evaluated_customers=totals["total"] - totals["censored"],
        censored_customers=totals["censored"],
        repurchase_threshold_days=totals["threshold"],
        risk_distribution=dist,
        model_auc=auc,
        model_reliability_note=note,
    )

@router.get("/customer-360/{customer_unique_id}", response_model=Customer360)
def get_customer_360(customer_unique_id: str, db: Connection = Depends(get_db)):
    row = db.execute(
        text("SELECT * FROM analytics.customer_360 WHERE customer_unique_id = :cid"),
        {"cid": customer_unique_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Client inconnu dans analytics.customer_360")
    return row

@router.get("/customer-360", response_model=list[Customer360])
def list_customer_360(
    risk_level: Optional[str] = None,
    segment: Optional[str] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Connection = Depends(get_db),
):
    query = "SELECT * FROM analytics.customer_360 WHERE NOT is_censored"
    params = {"limit": limit, "offset": offset}
    if risk_level:
        query += " AND proxy_risk_level = :risk_level"
        params["risk_level"] = risk_level
    if segment:
        query += " AND rfm_segment = :segment"
        params["segment"] = segment
    query += " ORDER BY proxy_risk_proba DESC LIMIT :limit OFFSET :offset"
    rows = db.execute(text(query), params).mappings().all()
    return rows

# --- Historique des métriques de modèle (fondation monitoring, append-only) ---

class MetricHistoryEntry(BaseModel):
    model_name: str
    model_version: str
    metric_name: str
    metric_value: float
    computed_at: str

@router.get("/model-metrics-history", response_model=list[MetricHistoryEntry])
def get_model_metrics_history(
    model_name: Optional[str] = None,
    limit: int = Query(200, le=2000),
    db: Connection = Depends(get_db),
):
    query = "SELECT model_name, model_version, metric_name, metric_value, computed_at::text FROM analytics.model_metrics_history"
    params = {"limit": limit}
    if model_name:
        query += " WHERE model_name = :model_name"
        params["model_name"] = model_name
    query += " ORDER BY computed_at DESC LIMIT :limit"
    rows = db.execute(text(query), params).mappings().all()
    return rows
