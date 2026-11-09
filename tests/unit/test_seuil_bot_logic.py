"""Tests unitaires purs (pas de DB) sur analytics/analyse_seuil_bot.py."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_analytics_module

# analyse_seuil_bot.py importe recommend_retailrocket.py en tête de module
# (`from recommend_retailrocket import ...`) : je dois la précharger pour
# que cet import se résolve via sys.modules plutôt que sys.path (voir
# load_analytics_module dans conftest.py).
load_analytics_module("recommend_retailrocket")
analyse_seuil_bot = load_analytics_module("analyse_seuil_bot")


def test_describe_distribution_counts_distinct_items_per_visitor():
    df = pd.DataFrame({
        "visitor_id": [1, 1, 1, 2, 2, 3],
        "item_id": ["a", "b", "a", "c", "d", "e"],
    })
    items_per_visitor = analyse_seuil_bot.describe_distribution(df)
    assert items_per_visitor.loc[1] == 2  # visiteur 1 : a, b (a compté une fois)
    assert items_per_visitor.loc[2] == 2
    assert items_per_visitor.loc[3] == 1


def test_sensitivity_table_reports_fewer_excluded_visitors_at_higher_threshold():
    """Propriété que je documente dans limitations-methodologiques.md :
    relever le seuil ne peut qu'exclure moins (ou autant) de visiteurs."""
    rows = []
    for v in range(10):
        rows += [(v, f"item{i}") for i in range(3)]  # 3 produits chacun
    one_bot = [(99, f"item{i}") for i in range(500)]  # un visiteur à 500 produits
    df = pd.DataFrame(rows + one_bot, columns=["visitor_id", "item_id"])

    saved_thresholds = analyse_seuil_bot.CANDIDATE_THRESHOLDS
    analyse_seuil_bot.CANDIDATE_THRESHOLDS = [10, 600]
    try:
        table = analyse_seuil_bot.sensitivity_table(df)
    finally:
        analyse_seuil_bot.CANDIDATE_THRESHOLDS = saved_thresholds

    low = table[table["seuil_max_produits"] == 10].iloc[0]
    high = table[table["seuil_max_produits"] == 600].iloc[0]
    assert low["visiteurs_exclus"] >= high["visiteurs_exclus"]
    assert high["visiteurs_exclus"] == 0  # seuil assez haut pour garder le "bot" aussi
