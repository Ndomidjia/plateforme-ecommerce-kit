"""Tests unitaires purs (pas de DB) sur analytics/customer_360_olist.py.

label_and_censor() et apply_category_fallback() ont été extraites pour ça :
la censure à droite est la partie la plus facile à se tromper dans ce
module (voir l'incident déjà documenté dans docs/journal-de-bord.md -- une
première version excluait à tort des clients ayant déjà racheté). Je fixe
ici, avec des dates fabriquées à la main, les cas limites qui auraient dû
attraper cet incident avant qu'il n'arrive en production."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_analytics_module

# customer_360_olist.py importe model_registry.py en tête de module : je
# dois la précharger pour que cet import se résolve via sys.modules (voir
# load_analytics_module dans conftest.py).
load_analytics_module("model_registry")
customer_360_olist = load_analytics_module("customer_360_olist")

REF = pd.Timestamp("2018-12-31")
THRESHOLD_DAYS = 126


def _row(first_purchase_at, deuxieme_achat, date_ref=REF):
    return {
        "customer_unique_id": "c",
        "first_purchase_at": pd.Timestamp(first_purchase_at),
        "deuxieme_achat": pd.Timestamp(deuxieme_achat) if deuxieme_achat else pd.NaT,
        "date_ref": pd.Timestamp(date_ref),
    }


def test_repurchase_within_window_is_retained_not_at_risk():
    df = pd.DataFrame([_row("2018-01-01", "2018-01-30")])  # 29 jours < 126
    out = customer_360_olist.label_and_censor(df, THRESHOLD_DAYS)
    assert out.loc[0, "label"] == 0  # retenu
    assert out.loc[0, "is_censored"] == False  # noqa: E712 -- issue déjà connue


def test_repurchase_after_window_is_at_risk_not_censored():
    df = pd.DataFrame([_row("2018-01-01", "2018-08-01")])  # ~212 jours > 126, et déjà connu
    out = customer_360_olist.label_and_censor(df, THRESHOLD_DAYS)
    assert out.loc[0, "label"] == 1  # à risque
    assert out.loc[0, "is_censored"] == False  # noqa: E712 -- l'issue EST connue (a racheté, juste tard)


def test_no_repurchase_but_enough_time_elapsed_is_at_risk_not_censored():
    """Cas limite de l'incident documenté : un client qui n'a PAS racheté
    mais dont la fenêtre d'observation est dépassée doit être classé
    "à risque", pas "censuré" -- son issue est connue (il n'a pas racheté
    dans la fenêtre), même si plus de temps s'est encore écoulé depuis."""
    df = pd.DataFrame([_row("2018-01-01", None, date_ref="2018-12-31")])  # ~365 jours, pas de 2e achat
    out = customer_360_olist.label_and_censor(df, THRESHOLD_DAYS)
    assert out.loc[0, "label"] == 1
    assert out.loc[0, "is_censored"] == False  # noqa: E712


def test_recent_customer_without_enough_elapsed_time_is_censored():
    """Un client dont la 1re commande est trop récente pour qu'on sache
    déjà s'il va racheter ou non dans la fenêtre doit être censuré, pas
    classé "à risque" par défaut -- c'est exactement le bug corrigé (voir
    journal de bord)."""
    df = pd.DataFrame([_row("2018-12-01", None, date_ref="2018-12-31")])  # 30 jours < 126, pas de 2e achat
    out = customer_360_olist.label_and_censor(df, THRESHOLD_DAYS)
    assert out.loc[0, "is_censored"] == True  # noqa: E712


def test_label_and_censor_does_not_mutate_input():
    df = pd.DataFrame([_row("2018-01-01", "2018-01-30")])
    original = df.copy()
    customer_360_olist.label_and_censor(df, THRESHOLD_DAYS)
    pd.testing.assert_frame_equal(df, original)


def test_category_fallback_fills_only_missing_recommendations():
    merged = pd.DataFrame({
        "customer_unique_id": ["c1", "c2", "c3"],
        "top_category": ["toys", "electronics", "electronics"],
        "recommended_category": ["games", None, None],
        "recommended_category_lift": [1.2, None, None],
    })
    out = customer_360_olist.apply_category_fallback(merged, global_top="bed_bath_table")
    assert out.loc[0, "recommended_category"] == "games"  # avait déjà une règle réelle, inchangé
    assert out.loc[1, "recommended_category"] == "bed_bath_table"  # repli appliqué
    assert out.loc[2, "recommended_category"] == "bed_bath_table"


def test_category_fallback_does_not_overwrite_when_top_category_is_already_global_top():
    """Si la catégorie principale du client EST déjà la plus vendue
    globalement et qu'aucune règle ne s'applique, le repli ne doit rien
    changer (elle y est déjà) -- évite une recommandation absurde
    "bed_bath_table -> bed_bath_table"."""
    merged = pd.DataFrame({
        "customer_unique_id": ["c1"],
        "top_category": ["bed_bath_table"],
        "recommended_category": [None],
        "recommended_category_lift": [None],
    })
    out = customer_360_olist.apply_category_fallback(merged, global_top="bed_bath_table")
    assert pd.isna(out.loc[0, "recommended_category"])
