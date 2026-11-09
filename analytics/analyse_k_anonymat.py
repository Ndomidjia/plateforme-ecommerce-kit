"""Mon analyse de k-anonymat sur ce qui reste après anonymisation RGPD
(DELETE /rgpd/churn/{id}, voir api/routers/rgpd.py et docs/rgpd.md).

Contexte (retour de soutenance) : dans docs/rgpd.md, je reconnaissais ne
jamais avoir mené d'analyse de k-anonymat sur les attributs comportementaux
restants (lifetime_value, login_frequency, etc.) après avoir retiré les
identifiants directs (age, gender, country, city) -- je ne savais donc pas
si mon anonymisation était réellement sûre, ou juste supposée l'être. Ce
script comble ce manque : pour un ensemble donné d'attributs restants
(generalisés par tranches, comme c'est l'usage en k-anonymat -- des valeurs
continues exactes ne se répètent presque jamais, donc les laisser telles
quelles rendrait k=1 pour tout le monde de façon triviale et peu informative),
je calcule, pour chaque client, la taille du groupe de clients qui partagent
exactement la même combinaison généralisée : c'est k. Plus k est petit, plus
le risque de ré-identification par singling-out est élevé (k=1 : la
combinaison identifie un client unique).

Je compare plusieurs tailles d'ensemble de quasi-identifiants (2, 4, 6
attributs) pour montrer l'effet classique en k-anonymat : plus on combine
d'attributs, même anodins pris un par un, plus le k minimum s'effondre.

N'écrit aucune table -- purement diagnostique, à lancer manuellement. Résultats
dans docs/assets/ (tableau + graphique), repris honnêtement dans docs/rgpd.md.
"""
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analytics.analyse_k_anonymat")

ASSETS_DIR = Path(__file__).resolve().parent.parent / "docs" / "assets"
N_BINS = 4  # quartiles : généralisation standard d'un attribut continu en k-anonymat

# Colonnes qui restent interrogeables après anonymisation (age/gender/country/
# city sont mises à NULL -- voir erase_churn_customer dans api/routers/rgpd.py).
# signup_quarter reste catégoriel en l'état (faible cardinalité, déjà une
# forme de généralisation) ; les autres sont continues, donc binées.
QI_SETS = {
    "2 attributs (signup_quarter + membership_years)": [
        "signup_quarter", "membership_years",
    ],
    "4 attributs (+ total_purchases + payment_method_diversity)": [
        "signup_quarter", "membership_years", "total_purchases", "payment_method_diversity",
    ],
    "6 attributs (+ lifetime_value + login_frequency)": [
        "signup_quarter", "membership_years", "total_purchases", "payment_method_diversity",
        "lifetime_value", "login_frequency",
    ],
}

RISK_THRESHOLDS = [1, 5, 10]  # k < seuil : combien de clients sont dans ce cas


def load_profiles(engine) -> pd.DataFrame:
    cols = sorted({c for cols in QI_SETS.values() for c in cols})
    df = pd.read_sql(f"SELECT customer_id, {', '.join(cols)} FROM churn.customer_profiles", engine)
    log.info("%d profils chargés (après simulation du retrait RGPD de age/gender/country/city)", len(df))
    return df


def generalize(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Généralise chaque colonne continue en quartiles (catégorie), laisse
    les colonnes déjà catégorielles (signup_quarter) telles quelles. Les
    valeurs manquantes forment leur propre catégorie ("manquant") plutôt que
    de rester NaN : un NaN de pandas ne s'auto-matche pas dans un groupby/
    merge, ce qui ferait perdre ces lignes de l'analyse en silence."""
    out = pd.DataFrame(index=df.index)
    for col in columns:
        if col == "signup_quarter":
            out[col] = df[col].astype(str).fillna("manquant")
        else:
            out[col] = pd.qcut(df[col], q=N_BINS, duplicates="drop").astype(str).fillna("manquant")
    return out


def k_anonymity_for(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    """Retourne, pour chaque ligne, k = la taille du groupe de clients qui
    partagent exactement la même combinaison généralisée de `columns`."""
    generalized = generalize(df, columns)
    group_sizes = generalized.groupby(columns, observed=True).size().rename("k")
    merged = generalized.merge(group_sizes, left_on=columns, right_index=True, how="left")
    return merged["k"].astype(int)


def summarize(df: pd.DataFrame) -> dict:
    return {
        "k_min": int(df.min()),
        "k_median": float(df.median()),
        # <= et pas < : je veux inclure k=1 (client unique, le cas le plus
        # grave) dans "pct_k_le_1", pas le faire disparaître parce que 1 n'est
        # pas strictement inférieur à 1.
        **{f"pct_k_le_{t}": round(100 * (df <= t).mean(), 2) for t in RISK_THRESHOLDS},
    }


def plot_k_distribution(k_by_set: dict[str, pd.Series]):
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    for label, k_values in k_by_set.items():
        sorted_k = k_values.sort_values().reset_index(drop=True)
        pct_population = 100 * (sorted_k.index + 1) / len(sorted_k)
        ax.plot(pct_population, sorted_k.values, label=label)
    ax.set_yscale("log")
    ax.axhline(5, color="#c44", linestyle="--", linewidth=1, label="k=5 (seuil usuel)")
    ax.set_xlabel("% des clients (triés par k croissant)")
    ax.set_ylabel("k (taille du groupe partageant la même combinaison, échelle log)")
    ax.set_title("k-anonymat sur churn.customer_profiles après simulation du retrait RGPD")
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_path = ASSETS_DIR / "k_anonymat_distribution.png"
    fig.savefig(out_path, dpi=150)
    log.info("Graphique écrit dans %s", out_path)


def main():
    # Import local, voir commentaire équivalent dans rfm_olist.py.
    from config import get_engine

    engine = get_engine()
    df = load_profiles(engine)

    rows = []
    k_by_set = {}
    for label, columns in QI_SETS.items():
        k_values = k_anonymity_for(df, columns)
        k_by_set[label] = k_values
        stats = summarize(k_values)
        stats["quasi_identifiants"] = label
        stats["nb_attributs"] = len(columns)
        rows.append(stats)
        log.info("%s -> %s", label, stats)

    table = pd.DataFrame(rows)[["quasi_identifiants", "nb_attributs", "k_min", "k_median",
                                 "pct_k_le_1", "pct_k_le_5", "pct_k_le_10"]]
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = ASSETS_DIR / "k_anonymat_resultats.csv"
    table.to_csv(out_csv, index=False)
    log.info("Tableau écrit dans %s", out_csv)
    print("\n" + table.to_string(index=False))

    plot_k_distribution(k_by_set)


if __name__ == "__main__":
    main()
