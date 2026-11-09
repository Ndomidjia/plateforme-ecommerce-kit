"""Ma vue client 360° unifiée sur Olist : RFM + proxy de risque de
non-réachat + sentiment + recommandation de catégorie, combinés pour chaque
client Olist.

Contexte (remarque de mon encadrant) : une fusion brute des 3 datasets
(Olist/Retailrocket/churn) est impossible — aucun identifiant commun entre
eux. J'ai écrit ce module pour répondre à sa demande de "fusionner les
données" au bon niveau : fusionner les RÉSULTATS d'analyse sur UNE MÊME
population (les clients Olist), en réutilisant la méthodologie que j'ai
validée sur le dataset churn labellisé (class_weight, validation croisée)
mais appliquée à un proxy que je construis depuis le comportement d'achat
réel d'Olist.

Point méthodologique fondamental que je ne dois jamais perdre de vue : il
n'existe PAS de vraie étiquette de churn pour les clients Olist
(contrairement au dataset churn.customer_profiles). Le "risque" que je
calcule ici est un PROXY — une estimation que je construis moi-même, pas une
vérité observée. Voir docs/limitations-methodologiques.md.

Ma v2 (revue critique que j'ai faite) par rapport à ma v1 :
- j'ai retiré review_score et delivery_delay_days des features : ce sont des
  informations connues APRÈS la livraison (parfois des semaines après le
  1er achat), donc inutilisables pour un vrai usage marketing "détecter tôt"
  -- je ne garde que ce qui est connu AU MOMENT du 1er achat.
- j'ai comparé 3 configurations (Random Forest avec/sans class_weight,
  Gradient Boosting) au lieu d'une seule config testée une fois -- ma v1
  concluait "quasiment aucun signal" après un seul essai, ce qui était
  insuffisant pour l'affirmer avec confiance.
- je journalise les métriques dans analytics.model_metrics_history
  (append-only) pour permettre un futur suivi de dérive, au lieu de
  seulement les afficher dans les logs et les perdre au recalcul suivant.
"""
import logging
from datetime import datetime

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, classification_report, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import text
import model_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analytics.customer_360_olist")

MODEL_NAME = "customer_360_proxy"
# "v2" = méthodologie (voir docstring ci-dessus) ; l'horodatage rend chaque
# exécution distincte pour mon model_registry (promotion/rollback, voir
# churn_model.py pour le même mécanisme).
MODEL_VERSION = f"proxy_risk_v2_{datetime.now():%Y%m%d_%H%M%S}"
REPURCHASE_PERCENTILE = 0.75  # que j'ai justifié empiriquement : voir étape 1

# Uniquement des variables connues AU MOMENT du 1er achat (voir docstring v2).
NUMERIC_FEATURES = ["first_order_value", "first_order_freight", "payment_installments"]
CATEGORICAL_FEATURES = ["payment_type", "customer_state", "first_category"]

# Candidats que je compare avant de choisir un modèle final, plutôt qu'une
# seule configuration testée une fois (voir docstring v2).
MODEL_CANDIDATES = {
    "random_forest_balanced": lambda: RandomForestClassifier(
        n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1),
    "random_forest_unweighted": lambda: RandomForestClassifier(
        n_estimators=300, random_state=42, n_jobs=-1),
    "gradient_boosting_balanced": lambda: HistGradientBoostingClassifier(
        class_weight="balanced", max_iter=300, random_state=42),
}


def compute_threshold(engine) -> int:
    """Seuil de non-réachat dérivé empiriquement (percentile 75 du délai
    observé chez les clients qui ont effectivement racheté) — pas une valeur
    choisie au hasard, conformément à la remarque de l'encadrant.

    Limite assumée : ce percentile est calculé sur les seuls clients ayant
    déjà racheté (les rachats très tardifs qui dépasseraient la fenêtre
    d'observation ne sont jamais vus). Une analyse de survie (Kaplan-Meier)
    traiterait cette censure plus rigoureusement au moment même du calcul du
    seuil ; non implémenté ici (dépendance supplémentaire, gain incertain vu
    le volume de données disponible), documenté comme limite plutôt que
    caché — voir docs/limitations-methodologiques.md."""
    df = pd.read_sql(text("""
        WITH premiere_commande AS (
            SELECT c.customer_unique_id, o.order_purchase_timestamp,
                   ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id ORDER BY o.order_purchase_timestamp) AS rang
            FROM olist.orders o JOIN olist.customers c ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'
        )
        SELECT EXTRACT(EPOCH FROM (p2.order_purchase_timestamp - p1.order_purchase_timestamp)) / 86400 AS jours
        FROM premiere_commande p1
        JOIN premiere_commande p2 ON p2.customer_unique_id = p1.customer_unique_id AND p2.rang = p1.rang + 1
        WHERE p1.rang = 1
    """), engine)
    threshold = int(round(df["jours"].quantile(REPURCHASE_PERCENTILE)))
    log.info("Délai de réachat (n=%d clients) : médiane=%.0fj, P75=%.0fj -> seuil retenu = %dj",
             len(df), df["jours"].median(), df["jours"].quantile(0.75), threshold)
    return threshold


def build_labeled_dataset(engine, threshold_days: int) -> pd.DataFrame:
    """Une ligne par client Olist avec commande livrée : features de la
    1re commande (connues au moment de l'achat uniquement) + label proxy
    (0=a racheté dans la fenêtre, 1=à risque) + indicateur de censure (pas
    encore assez de recul pour connaître l'issue).
    """
    query = text("""
        WITH first_order AS (
            SELECT DISTINCT ON (c.customer_unique_id)
                c.customer_unique_id, o.order_id, o.order_purchase_timestamp, c.customer_state
            FROM olist.orders o
            JOIN olist.customers c ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'
            ORDER BY c.customer_unique_id, o.order_purchase_timestamp
        ),
        second_order AS (
            SELECT c.customer_unique_id, MIN(o.order_purchase_timestamp) AS deuxieme_achat
            FROM olist.orders o
            JOIN olist.customers c ON c.customer_id = o.customer_id
            JOIN first_order fo ON fo.customer_unique_id = c.customer_unique_id
            WHERE o.order_status = 'delivered' AND o.order_purchase_timestamp > fo.order_purchase_timestamp
            GROUP BY c.customer_unique_id
        ),
        paiement AS (
            SELECT order_id, SUM(payment_value) AS total_value
            FROM olist.order_payments GROUP BY order_id
        ),
        moyen_paiement AS (
            SELECT DISTINCT ON (order_id) order_id, payment_type, payment_installments
            FROM olist.order_payments ORDER BY order_id, payment_sequential
        ),
        premier_article AS (
            SELECT DISTINCT ON (oi.order_id) oi.order_id, oi.freight_value,
                   COALESCE(ct.product_category_name_english, p.product_category_name) AS category
            FROM olist.order_items oi
            LEFT JOIN olist.products p ON p.product_id = oi.product_id
            LEFT JOIN olist.category_translation ct ON ct.product_category_name = p.product_category_name
            ORDER BY oi.order_id, oi.order_item_id
        ),
        ref AS (SELECT MAX(order_purchase_timestamp) AS date_ref FROM olist.orders WHERE order_status = 'delivered')
        SELECT
            fo.customer_unique_id,
            fo.customer_state,
            fo.order_purchase_timestamp AS first_purchase_at,
            pay.total_value AS first_order_value,
            pa.freight_value AS first_order_freight,
            mp.payment_type,
            mp.payment_installments,
            pa.category AS first_category,
            so.deuxieme_achat,
            ref.date_ref
        FROM first_order fo
        CROSS JOIN ref
        LEFT JOIN paiement pay ON pay.order_id = fo.order_id
        LEFT JOIN moyen_paiement mp ON mp.order_id = fo.order_id
        LEFT JOIN premier_article pa ON pa.order_id = fo.order_id
        LEFT JOIN second_order so ON so.customer_unique_id = fo.customer_unique_id
    """)
    df = pd.read_sql(query, engine, parse_dates=["first_purchase_at", "deuxieme_achat", "date_ref"])
    return label_and_censor(df, threshold_days)


def label_and_censor(df: pd.DataFrame, threshold_days: int) -> pd.DataFrame:
    """Logique pure (pas de DB) : calcule le label proxy (à risque / retenu)
    et l'indicateur de censure à partir des 3 colonnes de dates. Extrait de
    build_labeled_dataset() pour rester testable avec un DataFrame fabriqué
    à la main (voir tests/unit/test_customer_360_logic.py) -- la censure à
    droite est la partie la plus facile à se tromper dans ce module (voir
    l'incident déjà documenté dans docs/journal-de-bord.md)."""
    df = df.copy()
    threshold = pd.Timedelta(days=threshold_days)
    repurchased_in_window = df["deuxieme_achat"].notna() & (df["deuxieme_achat"] <= df["first_purchase_at"] + threshold)
    enough_elapsed = (df["date_ref"] - df["first_purchase_at"]) >= threshold

    df["is_censored"] = ~(repurchased_in_window | enough_elapsed)
    df["label"] = (~repurchased_in_window).astype(int)  # 1 = à risque (n'a pas racheté dans la fenêtre)
    return df


def build_preprocessor() -> ColumnTransformer:
    numeric_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        # sparse_output=False : HistGradientBoostingClassifier (un des 3
        # candidats que je compare) n'accepte pas les matrices creuses,
        # contrairement à RandomForestClassifier. Mon volume de données est
        # modeste (dizaines de milliers de lignes, ~100 colonnes après
        # encodage) : dense reste léger.
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer([
        ("num", numeric_pipe, NUMERIC_FEATURES),
        ("cat", categorical_pipe, CATEGORICAL_FEATURES),
    ])


def evaluate_candidate(name, model_factory, X_train, y_train, X_test, y_test) -> dict:
    pipeline = Pipeline([("prep", build_preprocessor()), ("model", model_factory())])
    pipeline.fit(X_train, y_train)
    proba = pipeline.predict_proba(X_test)[:, 1]
    pred = pipeline.predict(X_test)
    auc = roc_auc_score(y_test, proba)
    pr_auc = average_precision_score(y_test, proba)
    log.info("--- %s --- ROC-AUC=%.4f  PR-AUC=%.4f", name, auc, pr_auc)
    print(classification_report(y_test, pred, target_names=["retenu", "à risque"]))
    return {"name": name, "roc_auc": auc, "pr_auc": pr_auc}


def compute_sentiment_per_customer(engine) -> pd.DataFrame:
    return pd.read_sql(text("""
        SELECT c.customer_unique_id,
               AVG(s.review_score) AS avg_review_score,
               MODE() WITHIN GROUP (ORDER BY s.sentiment) AS dominant_sentiment
        FROM analytics.review_sentiment s
        JOIN olist.orders o ON o.order_id = s.order_id
        JOIN olist.customers c ON c.customer_id = o.customer_id
        GROUP BY c.customer_unique_id
    """), engine)


def compute_recommended_category(engine) -> pd.DataFrame:
    """Catégorie la plus achetée par client -> règle d'association (lift >= 1
    uniquement, cf. limite déjà documentée sur le market basket : la quasi
    totalité des règles ont un lift < 1 sur Olist). Repli sur la catégorie la
    plus vendue globalement quand aucune règle ne s'applique -- signalé
    comme tel (lift = NULL, à ne pas confondre avec une vraie règle de
    cross-sell) plutôt que de laisser 90% des clients sans rien."""
    top_category = pd.read_sql(text("""
        SELECT DISTINCT ON (c.customer_unique_id)
            c.customer_unique_id,
            COALESCE(ct.product_category_name_english, p.product_category_name) AS top_category
        FROM olist.order_items oi
        JOIN olist.orders o ON o.order_id = oi.order_id
        JOIN olist.customers c ON c.customer_id = o.customer_id
        LEFT JOIN olist.products p ON p.product_id = oi.product_id
        LEFT JOIN olist.category_translation ct ON ct.product_category_name = p.product_category_name
        WHERE o.order_status = 'delivered'
        GROUP BY c.customer_unique_id, COALESCE(ct.product_category_name_english, p.product_category_name)
        ORDER BY c.customer_unique_id, COUNT(*) DESC
    """), engine)

    rules = pd.read_sql(text(
        "SELECT antecedents AS top_category, consequents AS recommended_category, lift AS recommended_category_lift "
        "FROM analytics.association_rules WHERE lift >= 1"
    ), engine)

    merged = top_category.merge(rules, on="top_category", how="left")

    global_top = pd.read_sql(text("""
        SELECT COALESCE(ct.product_category_name_english, p.product_category_name) AS category, COUNT(*) AS n
        FROM olist.order_items oi
        JOIN olist.orders o ON o.order_id = oi.order_id
        LEFT JOIN olist.products p ON p.product_id = oi.product_id
        LEFT JOIN olist.category_translation ct ON ct.product_category_name = p.product_category_name
        WHERE o.order_status = 'delivered'
        GROUP BY category ORDER BY n DESC LIMIT 1
    """), engine)["category"].iloc[0]

    return apply_category_fallback(merged, global_top)


def apply_category_fallback(merged: pd.DataFrame, global_top: str) -> pd.DataFrame:
    """Logique pure (pas de DB) : complète par la catégorie la plus vendue
    globalement les clients sans règle d'association applicable. Extrait de
    compute_recommended_category() pour rester testable (voir
    tests/unit/test_customer_360_logic.py) -- c'est la limite déjà
    documentée du module (90% des recommandations finissent génériques)."""
    merged = merged.copy()
    fallback = merged["recommended_category"].isna() & merged["top_category"].notna() & (merged["top_category"] != global_top)
    merged.loc[fallback, "recommended_category"] = global_top
    return merged


def log_metrics_history(engine, metrics: dict):
    """Écrit dans analytics.model_metrics_history (append-only, jamais vidé)
    -- fondation pour un futur suivi de dérive dans le temps."""
    rows = pd.DataFrame([
        {"model_name": MODEL_NAME, "model_version": MODEL_VERSION, "metric_name": k, "metric_value": v}
        for k, v in metrics.items()
    ])
    rows.to_sql("model_metrics_history", engine, schema="analytics", if_exists="append", index=False)
    log.info("%d métriques journalisées dans analytics.model_metrics_history", len(rows))


def main():
    # Import local, voir commentaire équivalent dans rfm_olist.py.
    from config import get_engine

    engine = get_engine()

    log.info("=== Étape 1 : seuil de non-réachat (dérivé des données) ===")
    threshold_days = compute_threshold(engine)

    log.info("=== Étape 2 : construction du jeu de données labellisé (proxy) ===")
    df = build_labeled_dataset(engine, threshold_days)
    labeled = df[~df["is_censored"]].copy()
    log.info("%d clients au total, %d évaluables, %d trop récents (censurés)",
             len(df), len(labeled), df["is_censored"].sum())
    log.info("Répartition des classes (proxy) : \n%s", labeled["label"].value_counts().to_string())

    X = labeled[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = labeled["label"]

    log.info("=== Étape 3 : comparaison de %d configurations (pas une seule) ===", len(MODEL_CANDIDATES))
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    results = [evaluate_candidate(name, factory, X_train, y_train, X_test, y_test)
               for name, factory in MODEL_CANDIDATES.items()]
    best = max(results, key=lambda r: r["roc_auc"])
    log.info("Meilleur candidat : %s (ROC-AUC=%.4f) -- retenu pour le scoring final", best["name"], best["roc_auc"])

    metrics_to_log = {f"test_roc_auc__{r['name']}": r["roc_auc"] for r in results}
    metrics_to_log.update({f"test_pr_auc__{r['name']}": r["pr_auc"] for r in results})
    metrics_to_log["n_evaluated"] = len(labeled)
    metrics_to_log["n_censored"] = int(df["is_censored"].sum())
    metrics_to_log["pct_positive_class"] = float(y.mean())
    metrics_to_log["repurchase_threshold_days"] = threshold_days

    log.info("=== Étape 4 : scores honnêtes (validation croisée, %s) ===", best["name"])
    best_factory = MODEL_CANDIDATES[best["name"]]
    final_pipeline = Pipeline([("prep", build_preprocessor()), ("model", best_factory())])
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof_proba = cross_val_predict(final_pipeline, X, y, cv=cv, method="predict_proba", n_jobs=-1)[:, 1]
    labeled["proxy_risk_proba"] = oof_proba
    metrics_to_log["oof_roc_auc"] = roc_auc_score(y, oof_proba)

    # Clients trop récents (censurés) : je ré-entraîne mon modèle final sur
    # TOUT le jeu labellisé, puis je l'applique aux clients dont l'issue
    # n'est pas encore connue -- pas de fuite ici (contrairement à mon churn
    # scoring initial) : ces clients n'ont JAMAIS fait partie de
    # l'entraînement, c'est un vrai scoring hors échantillon, comme en
    # production.
    final_pipeline.fit(X, y)
    censored = df[df["is_censored"]].copy()
    if len(censored):
        censored["proxy_risk_proba"] = final_pipeline.predict_proba(censored[NUMERIC_FEATURES + CATEGORICAL_FEATURES])[:, 1]

    scored = pd.concat([labeled, censored], ignore_index=True)

    # Seuils de risque que je détermine sur la distribution réelle des
    # scores (tercile) plutôt que des seuils fixes arbitraires.
    q1, q2 = scored["proxy_risk_proba"].quantile([1 / 3, 2 / 3])
    scored["proxy_risk_level"] = pd.cut(scored["proxy_risk_proba"], bins=[-0.01, q1, q2, 1.01],
                                        labels=["low", "medium", "high"])
    log.info("Seuils de risque (terciles) : low<%.4f, medium<%.4f, high>=%.4f", q1, q2, q2)

    log.info("=== Étape 5 : sentiment + recommandation de catégorie (avec repli) ===")
    sentiment = compute_sentiment_per_customer(engine)
    recommendation = compute_recommended_category(engine)

    rfm = pd.read_sql("SELECT customer_unique_id, segment AS rfm_segment, recency_days, frequency, monetary "
                      "FROM analytics.rfm_segments", engine)

    out = (scored[["customer_unique_id", "is_censored", "proxy_risk_proba", "proxy_risk_level"]]
           .merge(rfm, on="customer_unique_id", how="left")
           .merge(sentiment, on="customer_unique_id", how="left")
           .merge(recommendation, on="customer_unique_id", how="left"))
    out["repurchase_threshold_days"] = threshold_days
    out["model_version"] = MODEL_VERSION

    cols = ["customer_unique_id", "rfm_segment", "recency_days", "frequency", "monetary",
            "repurchase_threshold_days", "is_censored", "proxy_risk_proba", "proxy_risk_level",
            "avg_review_score", "dominant_sentiment", "top_category", "recommended_category",
            "recommended_category_lift", "model_version"]
    out = out[cols]

    metrics_to_log["pct_with_recommendation"] = float(out["recommended_category"].notna().mean())

    # Même garde-fou que pour mon scoring churn (voir
    # analytics/model_registry.py) : je ne promeus une nouvelle version en
    # production que si elle n'est pas significativement moins bonne que la
    # version active. Ça répond directement à la question de soutenance "un
    # nouveau modèle moins bon écrase-t-il l'ancien sans rollback possible ?".
    decision = model_registry.decide_promotion(engine, MODEL_NAME, metrics_to_log["oof_roc_auc"])
    metrics_to_log["promoted"] = 1.0 if decision["promote"] else 0.0
    log.info("Décision de promotion (%s) : %s", MODEL_VERSION, decision["reason"])

    if decision["promote"]:
        model_registry.snapshot_before_promotion(engine, ["customer_360"])
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE analytics.customer_360"))
            out.to_sql("customer_360", conn, schema="analytics", if_exists="append", index=False, chunksize=5_000)
        model_registry.promote(engine, MODEL_NAME, MODEL_VERSION, metrics_to_log["oof_roc_auc"], decision)
        log.info("%d clients écrits dans analytics.customer_360 (%d évalués, %d censurés/récents, version active : %s)",
                 len(out), (~out["is_censored"]).sum(), out["is_censored"].sum(), MODEL_VERSION)
    else:
        model_registry.write_rejected_candidate(engine, "customer_360", out)
        log.warning(
            "Nouvelle version '%s' NON promue (%s) -- la version précédente reste active en "
            "production. Résultats disponibles pour inspection dans analytics.customer_360_candidate.",
            MODEL_VERSION, decision["reason"],
        )

    log_metrics_history(engine, metrics_to_log)


if __name__ == "__main__":
    main()
