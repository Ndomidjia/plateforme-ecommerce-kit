"""Tests unitaires purs (pas de DB) sur analytics/market_basket_olist.py.

compute_rules() a été extraite de main() pour ça : je construis des
transactions à la main (pas de vraie commande Olist) pour vérifier que le
calcul d'association (support/confiance/lift) se comporte comme attendu
sur un cas dont je connais la réponse à l'avance."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_analytics_module

market_basket_olist = load_analytics_module("market_basket_olist")


def test_perfectly_correlated_categories_get_high_lift():
    """A et B apparaissent toujours ensemble, jamais seuls : lift doit être
    nettement > 1 (association forte), confiance = 1 dans les deux sens."""
    transactions = [{"A", "B"}] * 20 + [{"C"}] * 20
    rules = market_basket_olist.compute_rules(transactions, min_support=0.01)

    ab_rules = rules[(rules["antecedents"] == "A") & (rules["consequents"] == "B")]
    assert len(ab_rules) == 1
    assert ab_rules.iloc[0]["confidence"] == 1.0
    assert ab_rules.iloc[0]["lift"] > 1.5


def test_independent_categories_get_lift_near_one():
    """A et C sont répartis indépendamment (moitié des transactions
    contiennent les deux, par pur hasard structuré) : leur lift doit rester
    proche de 1 (pas d'association réelle), cohérent avec mon résultat
    documenté sur Olist (quasi aucune paire de catégories au-dessus de 1)."""
    transactions = (
        [{"A", "C"}] * 25 + [{"A"}] * 25 + [{"C"}] * 25 + [{"D"}] * 25
    )
    rules = market_basket_olist.compute_rules(transactions, min_support=0.01)
    ac_rules = rules[(rules["antecedents"] == "A") & (rules["consequents"] == "C")]
    assert len(ac_rules) == 1
    assert 0.8 <= ac_rules.iloc[0]["lift"] <= 1.2


def test_higher_min_support_yields_fewer_or_equal_rules():
    transactions = [{"A", "B"}] * 15 + [{"A", "C"}] * 3 + [{"D"}] * 50
    loose = market_basket_olist.compute_rules(transactions, min_support=0.01)
    strict = market_basket_olist.compute_rules(transactions, min_support=0.2)
    assert len(strict) <= len(loose)


def test_rules_are_sorted_by_descending_lift():
    transactions = [{"A", "B"}] * 20 + [{"A", "C"}] * 2 + [{"B", "C"}] * 2 + [{"D"}] * 30
    rules = market_basket_olist.compute_rules(transactions, min_support=0.01)
    assert list(rules["lift"]) == sorted(rules["lift"], reverse=True)
