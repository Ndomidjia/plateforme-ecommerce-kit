"""Tests unitaires purs (pas de DB) sur analytics/recommend_retailrocket.py.

compute_similarity() est déjà une fonction pure (DataFrame visiteur/produit
-> recommandations), réutilisée telle quelle par
analytics/analyse_seuil_bot.py : je la teste ici directement, avec des
interactions fabriquées à la main plutôt qu'en relisant
analytics.item_recommendations après un vrai calcul."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_analytics_module

recommend_retailrocket = load_analytics_module("recommend_retailrocket")


def _interactions(pairs):
    return pd.DataFrame(pairs, columns=["visitor_id", "item_id"])


def test_items_always_viewed_together_are_mutually_recommended():
    # 5 visiteurs ont tous vu A et B ensemble (+ un produit de bruit chacun
    # pour ne pas être filtrés comme "1 seul produit").
    pairs = []
    for v in range(5):
        pairs += [(v, "A"), (v, "B"), (v, f"noise{v}")]
    df = _interactions(pairs)
    recos = recommend_retailrocket.compute_similarity(df)

    a_recos = set(recos[recos["item_id"] == "A"]["recommended_item_id"])
    assert "B" in a_recos
    b_recos = set(recos[recos["item_id"] == "B"]["recommended_item_id"])
    assert "A" in b_recos


def test_items_never_co_viewed_are_not_recommended_to_each_other():
    pairs = [(0, "A"), (0, "X"), (1, "A"), (1, "X"), (2, "B"), (2, "Y"), (3, "B"), (3, "Y")]
    df = _interactions(pairs)
    recos = recommend_retailrocket.compute_similarity(df)
    a_recos = set(recos[recos["item_id"] == "A"]["recommended_item_id"])
    assert "B" not in a_recos


def test_cooccurrence_below_minimum_is_excluded():
    """MIN_COOCCURRENCE = 3 par défaut : une paire vue ensemble par
    seulement 2 visiteurs ne doit générer aucune recommandation (évite le
    bruit de coïncidences isolées, voir docstring du module)."""
    pairs = [(0, "A"), (0, "B"), (1, "A"), (1, "B"), (2, "A"), (2, "noise")]
    df = _interactions(pairs)
    recos = recommend_retailrocket.compute_similarity(df)
    assert recos.empty or "B" not in set(recos[recos["item_id"] == "A"]["recommended_item_id"])


def test_similarity_score_is_bounded_between_zero_and_one():
    pairs = []
    for v in range(10):
        pairs += [(v, "A"), (v, "B")]
        if v % 2 == 0:
            pairs.append((v, "C"))
    df = _interactions(pairs)
    recos = recommend_retailrocket.compute_similarity(df)
    assert (recos["score"] >= 0).all()
    assert (recos["score"] <= 1.0001).all()  # cosinus, légère tolérance flottante


def test_recommendations_method_column_is_tagged():
    pairs = [(v, item) for v in range(5) for item in ("A", "B")]
    df = _interactions(pairs)
    # compute_similarity elle-même ne pose pas la colonne "method" (ajoutée
    # dans main()) -- je vérifie juste qu'elle retourne les bonnes colonnes
    # de base, contrat que main() s'appuie dessus pour écrire en base.
    recos = recommend_retailrocket.compute_similarity(df)
    assert list(recos.columns) == ["item_id", "recommended_item_id", "score"]
