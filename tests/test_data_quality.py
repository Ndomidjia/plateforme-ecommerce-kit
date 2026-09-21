"""Mes contrôles qualité post-ETL, automatisés (traduits depuis
sql/99_controles.sql, que je devais exécuter et relire à la main) +
quelques invariants supplémentaires sur les tables analytics.* que je
consomme dans l'API/le dashboard.

Je distingue explicitement deux cas très différents :
- table VIDE (0 ligne) -> `pytest.skip()`, pas un échec. C'est le cas en ma
  CI (voir .github/workflows/ci.yml) : je ne commite pas mes CSV Kaggle
  sources (data/raw/, volumineux, hors périmètre de licence de
  redistribution) donc aucun ETL n'a pu tourner sur le runner -- ma CI
  valide quand même le schéma SQL, l'API et le RBAC (tests/test_auth_rbac.py,
  tests/test_model_registry.py), juste pas la qualité de mes données
  réelles.
- table NON VIDE mais suspecte (volumes trop bas, valeurs hors plage) ->
  échec réel. C'est le seul cas qui compte pour moi en local/développement,
  où mon ETL a effectivement tourné sur mes vraies données.
"""
import pytest
from sqlalchemy import text

# Volumes attendus après un ETL complet (data/raw/{olist,retailrocket,churn}) :
# des minimums, pas des valeurs exactes, pour tolérer une mise à jour mineure
# du dataset source sans casser le test.
EXPECTED_MIN_ROWS = {
    "olist.orders": 90_000,
    "olist.order_items": 100_000,
    "olist.customers": 90_000,
    "retailrocket.events": 2_000_000,
    "churn.customer_profiles": 45_000,
}


def _count(engine, query: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(query)).scalar()


def test_expected_row_counts(engine):
    with engine.connect() as conn:
        for table, minimum in EXPECTED_MIN_ROWS.items():
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            if count == 0:
                pytest.skip(f"{table} vide -- ETL non lancé dans cet environnement (normal en CI, voir docs/tests.md)")
            assert count >= minimum, f"{table} : {count} lignes, {minimum} attendues au minimum (ETL incomplet ?)"


def test_no_orphan_orders(engine):
    """Toute commande Olist doit référencer un client existant."""
    if _count(engine, "SELECT COUNT(*) FROM olist.orders") == 0:
        pytest.skip("olist.orders vide -- ETL non lancé dans cet environnement")
    orphans = _count(engine, (
        "SELECT COUNT(*) FROM olist.orders o LEFT JOIN olist.customers c USING (customer_id) "
        "WHERE c.customer_id IS NULL"
    ))
    assert orphans == 0


def test_churn_scores_proba_in_valid_range(engine):
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT MIN(churn_proba), MAX(churn_proba), COUNT(*) FROM analytics.churn_scores"
        )).first()
    if row[2] == 0:
        pytest.skip("analytics.churn_scores vide -- lancer analytics/churn_model.py (normal en CI)")
    assert 0.0 <= row[0] and row[1] <= 1.0, f"churn_proba hors [0,1] : min={row[0]} max={row[1]}"


def test_churn_risk_level_matches_proba_bins(engine):
    """J'applique les bornes de risk_level côté Python (pd.cut,
    bins=[-0.01, 0.3, 0.6, 1.01], right=True donc bornes hautes incluses :
    low=(-0.01,0.3], medium=(0.3,0.6], high=(0.6,1.01]) au moment du scoring
    -- ce test vérifie qu'elles n'ont pas dérivé après un futur changement de
    ma part dans analytics/churn_model.py."""
    if _count(engine, "SELECT COUNT(*) FROM analytics.churn_scores") == 0:
        pytest.skip("analytics.churn_scores vide -- lancer analytics/churn_model.py (normal en CI)")
    with engine.connect() as conn:
        bad = conn.execute(text(
            "SELECT COUNT(*) FROM analytics.churn_scores WHERE "
            "(risk_level = 'low' AND churn_proba > 0.3) OR "
            "(risk_level = 'medium' AND (churn_proba <= 0.3 OR churn_proba > 0.6)) OR "
            "(risk_level = 'high' AND churn_proba <= 0.6)"
        )).scalar()
    assert bad == 0


def test_rfm_segments_have_no_nulls(engine):
    total = _count(engine, "SELECT COUNT(*) FROM analytics.rfm_segments")
    if total == 0:
        pytest.skip("analytics.rfm_segments vide -- lancer analytics/rfm_olist.py (normal en CI)")
    nulls = _count(engine, "SELECT COUNT(*) FROM analytics.rfm_segments WHERE segment IS NULL")
    assert nulls == 0


def test_association_rules_lift_is_positive(engine):
    if _count(engine, "SELECT COUNT(*) FROM analytics.association_rules") == 0:
        pytest.skip("analytics.association_rules vide -- lancer analytics/market_basket_olist.py (normal en CI)")
    bad = _count(engine, "SELECT COUNT(*) FROM analytics.association_rules WHERE lift <= 0")
    assert bad == 0


def test_sentiment_scores_are_valid_probabilities(engine):
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT MIN(sentiment_proba), MAX(sentiment_proba), COUNT(*) FROM analytics.review_sentiment"
        )).first()
    if row[2] == 0:
        pytest.skip("analytics.review_sentiment vide -- lancer analytics/sentiment_olist.py (normal en CI)")
    assert 0.0 <= row[0] and row[1] <= 1.0


def test_customer_360_risk_proba_in_valid_range(engine):
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT MIN(proxy_risk_proba), MAX(proxy_risk_proba), COUNT(*) FROM analytics.customer_360"
        )).first()
    if row[2] == 0:
        pytest.skip("analytics.customer_360 vide -- lancer analytics/customer_360_olist.py (normal en CI)")
    assert 0.0 <= row[0] and row[1] <= 1.0
