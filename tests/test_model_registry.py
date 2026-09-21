"""analytics/model_registry.py : garde-fou de promotion de modèle (répond à
la question de soutenance "un nouveau modèle moins bon écrase-t-il l'ancien
sans rollback possible ?"). Chargé par chemin direct (importlib) plutôt que
via sys.path : voir la note dans conftest.py sur le conflit de nom entre
api/config.py et analytics/config.py.
"""
import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

_MODULE_PATH = Path(__file__).resolve().parent.parent / "analytics" / "model_registry.py"
_spec = importlib.util.spec_from_file_location("model_registry", _MODULE_PATH)
model_registry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(model_registry)


@pytest.fixture
def dummy_model_name():
    """Un nom de modèle jetable et unique par test : n'interfère jamais avec
    les vraies entrées ('churn_scoring', 'customer_360_proxy') ni entre tests
    exécutés en parallèle."""
    name = f"pytest_dummy_{uuid.uuid4().hex[:8]}"
    yield name
    # nettoyage best-effort (les tables *_previous/*_candidate ne sont créées
    # que pour de vraies tables analytics.*, jamais pour ce nom factice)


@pytest.fixture(autouse=True)
def _cleanup_registry_row(engine, dummy_model_name):
    yield
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM analytics.model_registry WHERE model_name = :m"), {"m": dummy_model_name})


def test_first_run_always_promotes(engine, dummy_model_name):
    decision = model_registry.decide_promotion(engine, dummy_model_name, 0.60)
    assert decision["promote"] is True
    assert decision["active_before"] is None


def test_equal_or_better_metric_is_promoted(engine, dummy_model_name):
    first = model_registry.decide_promotion(engine, dummy_model_name, 0.80)
    model_registry.promote(engine, dummy_model_name, "v1", 0.80, first)

    second = model_registry.decide_promotion(engine, dummy_model_name, 0.81)
    assert second["promote"] is True
    assert second["active_before"]["active_version"] == "v1"


def test_regression_beyond_tolerance_is_rejected(engine, dummy_model_name):
    first = model_registry.decide_promotion(engine, dummy_model_name, 0.80)
    model_registry.promote(engine, dummy_model_name, "v1", 0.80, first)

    worse = 0.80 - model_registry.PROMOTION_TOLERANCE - 0.05
    second = model_registry.decide_promotion(engine, dummy_model_name, worse)
    assert second["promote"] is False


def test_regression_within_tolerance_is_still_promoted(engine, dummy_model_name):
    """Tolère le bruit naturel d'un ré-entraînement (même config -> métrique
    légèrement différente à chaque run), sans laisser passer une vraie
    régression -- voir PROMOTION_TOLERANCE dans analytics/model_registry.py."""
    first = model_registry.decide_promotion(engine, dummy_model_name, 0.80)
    model_registry.promote(engine, dummy_model_name, "v1", 0.80, first)

    slightly_worse = 0.80 - model_registry.PROMOTION_TOLERANCE + 0.001
    second = model_registry.decide_promotion(engine, dummy_model_name, slightly_worse)
    assert second["promote"] is True


def test_promote_records_previous_version_for_rollback(engine, dummy_model_name):
    first = model_registry.decide_promotion(engine, dummy_model_name, 0.80)
    model_registry.promote(engine, dummy_model_name, "v1", 0.80, first)

    active = model_registry.get_active(engine, dummy_model_name)
    assert active["active_version"] == "v1"
    assert active["has_backup"] is False  # premier déploiement : rien à sauvegarder

    second = model_registry.decide_promotion(engine, dummy_model_name, 0.82)
    model_registry.promote(engine, dummy_model_name, "v2", 0.82, second)

    active = model_registry.get_active(engine, dummy_model_name)
    assert active["active_version"] == "v2"
    assert active["has_backup"] is True
    assert active["previous_version"] == "v1"
    assert active["previous_metric"] == 0.80
