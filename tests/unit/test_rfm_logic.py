"""Tests unitaires purs (pas de DB) sur analytics/rfm_olist.py.

Je réponds ici à la question de soutenance "la logique interne des scripts
analytics/*.py n'est testée qu'à travers leur résultat final en base" :
score_rfm() est une fonction pure (DataFrame -> DataFrame), je la teste
directement avec des données fabriquées à la main plutôt qu'en relisant la
table analytics.rfm_segments après coup (c'est déjà fait dans
tests/test_data_quality.py, à un autre niveau)."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_analytics_module

rfm_olist = load_analytics_module("rfm_olist")


def _make_df(rows):
    return pd.DataFrame(rows, columns=["customer_unique_id", "recency_days", "frequency", "monetary"])


def _make_varied_df(n=5, **overrides):
    """score_rfm calcule toujours r_score/m_score par quintiles (pd.qcut) en
    plus de f_score : il me faut donc au moins 5 valeurs distinctes de
    recency_days/monetary pour que qcut puisse découper, même quand le test
    ne regarde que f_score (c'est une vraie contrainte de la fonction,
    jamais un problème en pratique avec des dizaines de milliers de
    clients réels, mais mes données fabriquées doivent la respecter)."""
    rows = [[f"c{i}", 10 + i * 5, overrides.get("frequency", [1] * n)[i], 50.0 + i * 20] for i in range(n)]
    return _make_df(rows)


def test_mono_achat_gets_lowest_frequency_score():
    """97% des clients Olist n'ont commandé qu'une fois (voir
    limitations-methodologiques.md) : f_score=1 pour frequency=1."""
    df = _make_varied_df(5, frequency=[1, 1, 1, 1, 1])
    out = rfm_olist.score_rfm(df)
    assert (out["f_score"] == 1).all()


def test_two_orders_gets_medium_frequency_score():
    df = _make_varied_df(5, frequency=[2, 2, 2, 2, 2])
    out = rfm_olist.score_rfm(df)
    assert (out["f_score"] == 3).all()


def test_three_or_more_orders_gets_highest_frequency_score():
    df = _make_varied_df(5, frequency=[3, 4, 5, 6, 7])
    out = rfm_olist.score_rfm(df)
    assert (out["f_score"] == 5).all()


def test_recent_and_frequent_customer_is_champion():
    # 5 clients pour que qcut (quintiles) ait de quoi découper ; le dernier
    # est le plus récent (recency_days minimal) et le plus dépensier.
    rows = [[f"c{i}", 100 - i * 10, 1, 50.0 + i * 10] for i in range(5)]
    df = _make_df(rows)
    df.loc[4, "frequency"] = 5  # le client le plus récent devient aussi fréquent -> Champion
    out = rfm_olist.score_rfm(df)
    champion_row = out[out["customer_unique_id"] == "c4"].iloc[0]
    assert champion_row["segment"] == "Champions"


def test_old_and_infrequent_customer_is_dormant():
    rows = [[f"c{i}", 100 - i * 10, 1, 50.0 + i * 10] for i in range(5)]
    df = _make_df(rows)
    out = rfm_olist.score_rfm(df)
    # c0 a la plus grande récence (donc la moins récente) et frequency=1 (f_score=1)
    dormant_row = out[out["customer_unique_id"] == "c0"].iloc[0]
    assert dormant_row["segment"] == "En sommeil"


def test_segment_is_always_one_of_the_known_categories():
    rows = [[f"c{i}", i + 1, (i % 3) + 1, 20.0 + i] for i in range(10)]
    df = _make_df(rows)
    out = rfm_olist.score_rfm(df)
    known = {"Champions", "Fidèles", "Nouveaux / Prometteurs", "À risque", "En sommeil", "Autres"}
    assert set(out["segment"].unique()) <= known


def test_score_rfm_does_not_mutate_its_input():
    df = _make_varied_df(5, frequency=[1, 1, 1, 1, 1])
    original = df.copy()
    rfm_olist.score_rfm(df)
    pd.testing.assert_frame_equal(df, original)
