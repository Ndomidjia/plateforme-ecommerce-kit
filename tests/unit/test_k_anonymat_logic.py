"""Tests unitaires purs (pas de DB) sur analytics/analyse_k_anonymat.py."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_analytics_module

analyse_k_anonymat = load_analytics_module("analyse_k_anonymat")


def test_generalize_keeps_categorical_column_as_is():
    df = pd.DataFrame({"signup_quarter": ["Q1", "Q2", "Q1"]})
    out = analyse_k_anonymat.generalize(df, ["signup_quarter"])
    assert list(out["signup_quarter"]) == ["Q1", "Q2", "Q1"]


def test_generalize_bins_continuous_column_into_quartiles():
    df = pd.DataFrame({"lifetime_value": list(range(100))})
    out = analyse_k_anonymat.generalize(df, ["lifetime_value"])
    assert out["lifetime_value"].nunique() <= analyse_k_anonymat.N_BINS


def test_generalize_turns_missing_values_into_their_own_category():
    """Un NaN de pandas ne se auto-matche pas dans un groupby/merge -- sans
    ce garde-fou, ces lignes disparaîtraient silencieusement du calcul de k
    (voir le commentaire dans generalize())."""
    df = pd.DataFrame({"signup_quarter": ["Q1", np.nan, "Q2"]})
    out = analyse_k_anonymat.generalize(df, ["signup_quarter"])
    assert out["signup_quarter"].isna().sum() == 0
    assert "manquant" in out["signup_quarter"].values


def test_k_anonymity_for_unique_combination_gives_k_equal_one():
    df = pd.DataFrame({
        "signup_quarter": ["Q1", "Q1", "Q2"],
        "membership_years": [1.0, 1.0, 5.0],
    })
    k = analyse_k_anonymat.k_anonymity_for(df, ["signup_quarter", "membership_years"])
    assert k.iloc[2] == 1  # Q2/5.0 n'apparaît qu'une fois
    assert k.iloc[0] == 2 and k.iloc[1] == 2  # Q1/1.0 apparaît deux fois


def test_fewer_quasi_identifiers_never_decreases_k():
    """Propriété fondamentale du k-anonymat que je documente dans
    docs/rgpd.md : ajouter des attributs ne peut qu'affiner les groupes,
    jamais les agrandir."""
    df = pd.DataFrame({
        "signup_quarter": ["Q1", "Q1", "Q1", "Q2"],
        "membership_years": [1.0, 1.0, 5.0, 5.0],
    })
    k_narrow = analyse_k_anonymat.k_anonymity_for(df, ["signup_quarter"])
    k_wide = analyse_k_anonymat.k_anonymity_for(df, ["signup_quarter", "membership_years"])
    assert (k_wide <= k_narrow).all()


def test_summarize_reports_k_equal_one_in_le_1_bucket():
    k_values = pd.Series([1, 1, 5, 20])
    stats = analyse_k_anonymat.summarize(k_values)
    assert stats["k_min"] == 1
    assert stats["pct_k_le_1"] == 50.0  # 2 sur 4
    assert stats["pct_k_le_5"] == 75.0  # 3 sur 4
