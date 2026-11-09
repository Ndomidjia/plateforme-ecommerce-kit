"""Tests unitaires purs (pas de DB, pas d'entraînement de modèle) sur
analytics/churn_model.py.

proba_to_risk_level() a été extraite de main() pour ça : je vérifie les
paliers low/medium/high directement sur des probabilités fabriquées, sans
entraîner de Random Forest (qui prend plusieurs minutes, voir
docs/tests.md). Les bornes exactes (0.3, 0.6) sont aussi vérifiées côté
base dans tests/test_data_quality.py::test_churn_risk_level_matches_proba_bins
-- complémentaire, pas redondant : celui-ci teste la fonction avant
écriture, l'autre vérifie que rien n'a dérivé une fois en base."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_analytics_module

# churn_model.py importe model_registry.py en tête de module : je dois la
# précharger pour que cet import se résolve via sys.modules (voir
# load_analytics_module dans conftest.py).
load_analytics_module("model_registry")
churn_model = load_analytics_module("churn_model")


def test_low_risk_boundary_is_inclusive():
    # bins=[-0.01, 0.3, 0.6, 1.01], right=True -> 0.3 pile inclus dans "low"
    result = churn_model.proba_to_risk_level([0.3])
    assert result[0] == "low"


def test_just_above_low_boundary_is_medium():
    result = churn_model.proba_to_risk_level([0.3001])
    assert result[0] == "medium"


def test_medium_risk_boundary_is_inclusive():
    result = churn_model.proba_to_risk_level([0.6])
    assert result[0] == "medium"


def test_just_above_medium_boundary_is_high():
    result = churn_model.proba_to_risk_level([0.6001])
    assert result[0] == "high"


def test_zero_proba_is_low_and_near_one_is_high():
    result = churn_model.proba_to_risk_level([0.0, 0.999])
    assert result[0] == "low"
    assert result[1] == "high"


def test_all_three_levels_are_reachable():
    result = churn_model.proba_to_risk_level([0.1, 0.45, 0.9])
    assert list(result) == ["low", "medium", "high"]
