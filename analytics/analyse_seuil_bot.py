"""Mon analyse de sensibilité du seuil MAX_ITEMS_PER_VISITOR (recommend_retailrocket.py).

Contexte (retour de soutenance) : mon jury m'a fait remarquer que le seuil
de 200 produits distincts par visiteur, que j'utilise pour exclure les
comportements de bot/crawler, n'était justifié dans mon code que par une
phrase ("118 visiteurs sur 1,4M") sans montrer la distribution réelle qui
m'a mené à ce choix, ni vérifier que le résultat final (couverture du
catalogue, volume de recommandations) est stable autour de cette valeur --
j'ai écrit ce script pour combler ce manque :

1. je trace la distribution du nombre de produits distincts consultés par
   visiteur, et je cherche une cassure nette qui séparerait naturellement
   des visiteurs humains d'un comportement de bot ;
2. je compare, pour plusieurs seuils candidats (100/150/200/300/500), le
   volume de données conservées et le résultat final produit par mon
   pipeline de recommandation (recommend_retailrocket.py) -- si le résultat
   est stable, mon seuil est robuste dans cette plage ; s'il varie
   fortement, mon choix de 200 est en réalité arbitraire et je dois le
   documenter comme tel plutôt que le présenter comme une décision
   technique solide (formulation reprise directement du retour de
   soutenance).

J'écris mes résultats dans docs/assets/ (graphique + tableau) et je ne
touche à aucune table de la base -- purement diagnostique, à lancer
manuellement, pas dans run_all.py ni dans le recalcul à la demande de
l'admin.
"""
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from recommend_retailrocket import MIN_COOCCURRENCE, MIN_ITEMS_PER_VISITOR, TOP_N, compute_similarity

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analytics.analyse_seuil_bot")

ASSETS_DIR = Path(__file__).resolve().parent.parent / "docs" / "assets"
CANDIDATE_THRESHOLDS = [100, 150, 200, 300, 500]


def load_raw_interactions(engine) -> pd.DataFrame:
    df = pd.read_sql("SELECT DISTINCT visitor_id, item_id FROM retailrocket.events", engine)
    log.info("%d interactions brutes (visiteur, produit) distinctes", len(df))
    return df


def describe_distribution(df: pd.DataFrame) -> pd.Series:
    items_per_visitor = df.groupby("visitor_id")["item_id"].nunique()
    log.info("%d visiteurs au total", len(items_per_visitor))

    percentiles = [0.50, 0.75, 0.90, 0.95, 0.99, 0.995, 0.999, 0.9999, 1.0]
    desc = items_per_visitor.quantile(percentiles)
    log.info("Distribution du nb de produits distincts par visiteur :\n%s", desc.to_string())

    for t in CANDIDATE_THRESHOLDS:
        n_above = (items_per_visitor > t).sum()
        log.info("  > %d produits : %d visiteurs (%.4f%% du total)", t, n_above, 100 * n_above / len(items_per_visitor))

    return items_per_visitor


def plot_distribution(items_per_visitor: pd.Series):
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))

    # Histogramme échelle log (axe Y) : je rends visible la "cassure" -- la
    # masse de visiteurs humains s'effondre rapidement, et une longue traîne
    # fine de comportements atypiques (bots probables) s'étend au-delà.
    axes[0].hist(items_per_visitor.clip(upper=1000), bins=200, color="#4C72B0")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Produits distincts consultés par visiteur (plafonné à 1000 pour lisibilité)")
    axes[0].set_ylabel("Nombre de visiteurs (échelle log)")
    axes[0].set_title("Distribution -- échelle log")
    for t, color in zip(CANDIDATE_THRESHOLDS, ["#999", "#666", "#c44", "#666", "#999"]):
        axes[0].axvline(t, color=color, linestyle="--", linewidth=1)
        axes[0].text(t, axes[0].get_ylim()[1] * 0.6, str(t), rotation=90, fontsize=8, color=color)

    # Fonction de survie (log-log) : la queue d'une distribution "normale"
    # de navigation suit une loi de puissance à peu près rectiligne en
    # log-log ; un coude / une rupture de pente me signalerait un second
    # régime (bot) distinct plutôt qu'une simple continuation de la même
    # queue.
    sorted_vals = np.sort(items_per_visitor.values)[::-1]
    rank = np.arange(1, len(sorted_vals) + 1)
    survival = rank / len(sorted_vals)
    axes[1].loglog(sorted_vals, survival, color="#4C72B0", linewidth=1)
    axes[1].set_xlabel("Produits distincts consultés (log)")
    axes[1].set_ylabel("P(X >= x) (log)")
    axes[1].set_title("Fonction de survie -- échelle log-log")
    for t, color in zip(CANDIDATE_THRESHOLDS, ["#999", "#666", "#c44", "#666", "#999"]):
        axes[1].axvline(t, color=color, linestyle="--", linewidth=1)

    fig.suptitle("Nombre de produits distincts consultés par visiteur (Retailrocket)")
    fig.tight_layout()
    out_path = ASSETS_DIR / "seuil_bot_distribution.png"
    fig.savefig(out_path, dpi=150)
    log.info("Graphique écrit dans %s", out_path)


def sensitivity_table(df: pd.DataFrame) -> pd.DataFrame:
    """Pour chaque seuil candidat, je ré-exécute le pipeline complet de
    recommend_retailrocket.py (mêmes filtres, même calcul de similarité) et
    je mesure l'effet sur le résultat final -- pas seulement sur le nombre de
    lignes filtrées en amont."""
    rows = []
    for max_items in CANDIDATE_THRESHOLDS:
        items_per_visitor = df.groupby("visitor_id")["item_id"].transform("count")
        keep = items_per_visitor.between(MIN_ITEMS_PER_VISITOR, max_items)
        filtered = df[keep]

        n_excluded_visitors = df["visitor_id"].nunique() - filtered["visitor_id"].nunique()

        recos = compute_similarity(filtered)
        total_items = df["item_id"].nunique()
        coverage_pct = 100 * recos["item_id"].nunique() / total_items

        rows.append({
            "seuil_max_produits": max_items,
            "visiteurs_conserves": filtered["visitor_id"].nunique(),
            "visiteurs_exclus": n_excluded_visitors,
            "pct_visiteurs_exclus": round(100 * n_excluded_visitors / df["visitor_id"].nunique(), 4),
            "produits_conserves": filtered["item_id"].nunique(),
            "paires_reco_generees": len(recos),
            "produits_couverts": recos["item_id"].nunique(),
            "couverture_catalogue_pct": round(coverage_pct, 2),
        })
        log.info("seuil=%d -> %s", max_items, rows[-1])

    return pd.DataFrame(rows)


def main():
    # Import local, voir commentaire équivalent dans rfm_olist.py.
    from config import get_engine

    engine = get_engine()
    df = load_raw_interactions(engine)

    items_per_visitor = describe_distribution(df)
    plot_distribution(items_per_visitor)

    log.info("=== Comparaison de %d seuils candidats (recalcul complet du pipeline pour chacun) ===",
              len(CANDIDATE_THRESHOLDS))
    table = sensitivity_table(df)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = ASSETS_DIR / "seuil_bot_sensibilite.csv"
    table.to_csv(out_csv, index=False)
    log.info("Tableau de sensibilité écrit dans %s", out_csv)
    print("\n" + table.to_string(index=False))


if __name__ == "__main__":
    main()
