"""Tests unitaires purs (pas de DB) sur analytics/funnel_retailrocket.py."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_analytics_module

funnel_retailrocket = load_analytics_module("funnel_retailrocket")


def test_add_rates_computes_expected_ratios():
    df = pd.DataFrame({"views": [100], "addtocarts": [25], "transactions": [5]})
    out = funnel_retailrocket.add_rates(df)
    assert out.loc[0, "view_to_cart_rate"] == 0.25
    assert out.loc[0, "cart_to_buy_rate"] == 0.2


def test_add_rates_handles_zero_views_without_division_error():
    """Un visiteur en moins ne doit jamais produire une division par zéro
    qui ferait planter le calcul (voir .where(... > 0) dans add_rates)."""
    df = pd.DataFrame({"views": [0], "addtocarts": [0], "transactions": [0]})
    out = funnel_retailrocket.add_rates(df)
    assert pd.isna(out.loc[0, "view_to_cart_rate"])
    assert pd.isna(out.loc[0, "cart_to_buy_rate"])


def test_add_rates_handles_views_without_any_cart_addition():
    df = pd.DataFrame({"views": [50], "addtocarts": [0], "transactions": [0]})
    out = funnel_retailrocket.add_rates(df)
    assert out.loc[0, "view_to_cart_rate"] == 0.0
    assert pd.isna(out.loc[0, "cart_to_buy_rate"])  # 0/0 -> NaN, pas une erreur


def test_add_rates_on_multiple_weeks_is_vectorized_correctly():
    df = pd.DataFrame({
        "views": [100, 200, 0],
        "addtocarts": [10, 50, 0],
        "transactions": [2, 10, 0],
    })
    out = funnel_retailrocket.add_rates(df)
    np.testing.assert_allclose(out["view_to_cart_rate"].iloc[:2], [0.1, 0.25])
    np.testing.assert_allclose(out["cart_to_buy_rate"].iloc[:2], [0.2, 0.2])
    assert pd.isna(out["view_to_cart_rate"].iloc[2])
