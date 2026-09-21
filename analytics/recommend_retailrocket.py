"""Ma recommandation collaborative item-item sur Retailrocket.

Principe : je considère que deux produits sont "similaires" s'ils sont
souvent consultés par les mêmes visiteurs (co-occurrence), mesurée par une
similarité cosinus sur la matrice binaire visiteur x produit. Approche
classique "les clients qui ont consulté X ont aussi consulté Y", tous types
d'événements confondus (view/addtocart/transaction) : ce qui compte ici est
la co-visite, pas la conversion (que je traite déjà dans le funnel).

Mon nettoyage préalable :
- j'exclus les visiteurs à >200 produits distincts (comportement de
  bot/crawler : 118 visiteurs sur 1,4M, mais des millions de paires
  mécaniques si je les garde). J'ai testé ce seuil par analyse de
  sensibilité, je ne l'ai pas choisi au jugé : voir
  analytics/analyse_seuil_bot.py et docs/limitations-methodologiques.md
  ("Le seuil de 200 produits, que j'ai testé — pas juste affirmé") -- ma
  distribution réelle n'a pas de cassure nette à 200 (longue traîne
  continue), mais mon résultat final (couverture catalogue, volume de
  recommandations) est stable sur la plage 100-500 que j'ai testée, ce qui
  rend ce choix robuste sans être pour autant "optimal" au sens strict.
- j'exclus les visiteurs à 1 seul produit distinct : ils ne contribuent à
  aucune co-occurrence, inutile de les charger en mémoire. C'est en réalité
  ce filtre, pas la borne haute, qui explique l'essentiel des 79,5% de
  visiteurs que j'exclus (voir mon analyse de sensibilité).
"""
import logging
import numpy as np
import pandas as pd
from scipy import sparse
from sqlalchemy import text
from config import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analytics.recommend_retailrocket")

MIN_ITEMS_PER_VISITOR = 2
MAX_ITEMS_PER_VISITOR = 200

# Requête que j'ai volontairement gardée simple : mon filtrage (2..200
# produits par visiteur) se fait ensuite côté pandas. Ma première version
# avec un WHERE visitor_id IN (sous-requête GROUP BY/HAVING) a produit un
# plan d'exécution pathologique (>1h30 sans terminer) — ce DISTINCT seul
# reste rapide.
QUERY = "SELECT DISTINCT visitor_id, item_id FROM retailrocket.events"

def load_interactions(engine) -> pd.DataFrame:
    df = pd.read_sql(QUERY, engine)
    log.info("%d interactions brutes (visiteur, produit) distinctes", len(df))

    items_per_visitor = df.groupby("visitor_id")["item_id"].transform("count")
    keep = items_per_visitor.between(MIN_ITEMS_PER_VISITOR, MAX_ITEMS_PER_VISITOR)
    df = df[keep]

    log.info("%d interactions retenues après filtrage (%d..%d produits/visiteur) : %d visiteurs, %d produits",
              len(df), MIN_ITEMS_PER_VISITOR, MAX_ITEMS_PER_VISITOR,
              df["visitor_id"].nunique(), df["item_id"].nunique())
    return df

MIN_COOCCURRENCE = 3  # minimum de visiteurs communs pour retenir une paire (évite le bruit de coïncidences isolées)
TOP_N = 10            # nombre de recommandations conservées par produit

def compute_similarity(df: pd.DataFrame) -> pd.DataFrame:
    visitor_codes, _ = pd.factorize(df["visitor_id"])
    item_codes, item_index = pd.factorize(df["item_id"])

    # matrice binaire visiteur x produit (creuse)
    M = sparse.csr_matrix(
        (np.ones(len(df), dtype=np.float32), (visitor_codes, item_codes)),
        shape=(visitor_codes.max() + 1, len(item_index)),
    )

    # co_occurrence[i, j] = nombre de visiteurs ayant interagi à la fois avec i et j
    co_occurrence = (M.T @ M).tocsr()
    norms = np.sqrt(co_occurrence.diagonal())  # co_occurrence[i,i] = nb visiteurs de l'item i

    co_occurrence = co_occurrence.tocoo()
    log.info("Matrice de co-occurrence : %d produits, %d paires non nulles",
             len(item_index), co_occurrence.nnz)

    rows, cols, counts = co_occurrence.row, co_occurrence.col, co_occurrence.data
    mask = (rows != cols) & (counts >= MIN_COOCCURRENCE)
    rows, cols, counts = rows[mask], cols[mask], counts[mask]

    scores = counts / (norms[rows] * norms[cols])
    log.info("%d paires après filtre (co-occurrence >= %d, hors diagonale)", len(scores), MIN_COOCCURRENCE)

    sims = pd.DataFrame({"item_code": rows, "reco_code": cols, "score": scores})
    top = sims.sort_values("score", ascending=False).groupby("item_code").head(TOP_N)

    top = top.assign(
        item_id=item_index[top["item_code"]],
        recommended_item_id=item_index[top["reco_code"]],
    )
    return top[["item_id", "recommended_item_id", "score"]].reset_index(drop=True)

def main():
    engine = get_engine()
    interactions = load_interactions(engine)
    recos = compute_similarity(interactions)
    log.info("%d recommandations générées (%d produits couverts)",
             len(recos), recos["item_id"].nunique())

    recos["method"] = "item-item CF"

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE analytics.item_recommendations"))
        recos.to_sql("item_recommendations", conn, schema="analytics",
                     if_exists="append", index=False, chunksize=10_000)
    log.info("%d lignes écrites dans analytics.item_recommendations", len(recos))

if __name__ == "__main__":
    main()
