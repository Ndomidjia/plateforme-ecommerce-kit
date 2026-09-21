"""Module RFM (Récence / Fréquence / Montant) sur le socle transactionnel Olist.

Étape 1 : extraction des valeurs brutes par client, avant scoring.
On ne retient que les commandes livrées ('delivered') : une commande annulée
ou jamais aboutie ne reflète pas un comportement d'achat réel.

Le regroupement se fait sur customer_unique_id, pas customer_id : dans Olist,
customer_id change à chaque commande, seul customer_unique_id identifie le
client physique.
"""
import logging
import pandas as pd
from sqlalchemy import text
from config import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analytics.rfm_olist")

QUERY = """
SELECT
    c.customer_unique_id,
    MAX(o.order_purchase_timestamp) AS last_purchase,
    COUNT(DISTINCT o.order_id)      AS frequency,
    SUM(p.payment_value)            AS monetary
FROM olist.orders o
JOIN olist.customers c      ON c.customer_id = o.customer_id
JOIN olist.order_payments p ON p.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_unique_id
"""

def extract_raw_rfm(engine) -> pd.DataFrame:
    df = pd.read_sql(QUERY, engine, parse_dates=["last_purchase"])
    # date de référence = jour suivant la dernière commande livrée du dataset
    # (les données sont historiques, "aujourd'hui" n'a pas de sens ici)
    reference_date = df["last_purchase"].max() + pd.Timedelta(days=1)
    df["recency_days"] = (reference_date - df["last_purchase"]).dt.days
    return df

def score_rfm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # R et M : variables continues -> quintiles classiques (1=pire, 5=meilleur)
    df["r_score"] = pd.qcut(df["recency_days"], 5, labels=[5, 4, 3, 2, 1]).astype(int)
    df["m_score"] = pd.qcut(df["monetary"], 5, labels=[1, 2, 3, 4, 5]).astype(int)

    # F : 97 % des clients ont frequency=1, un quintile serait artificiel.
    # Mapping manuel qui encode le seul signal réel : client mono-achat / a
    # commandé 2 fois / client récurrent (3+).
    df["f_score"] = df["frequency"].apply(lambda f: 1 if f == 1 else (3 if f == 2 else 5))

    def segment(row):
        r, f = row["r_score"], row["f_score"]
        if r >= 4 and f >= 4:
            return "Champions"
        if r >= 3 and f >= 4:
            return "Fidèles"
        if r >= 4 and f < 4:
            return "Nouveaux / Prometteurs"
        if r <= 2 and f >= 4:
            return "À risque"
        if r <= 2 and f <= 2:
            return "En sommeil"
        return "Autres"

    df["segment"] = df.apply(segment, axis=1)
    return df

def main():
    engine = get_engine()
    df = extract_raw_rfm(engine)
    log.info("%d clients avec au moins une commande livrée", len(df))

    df = score_rfm(df)
    log.info("Répartition des segments :\n%s", df["segment"].value_counts().to_string())

    out = df[["customer_unique_id", "recency_days", "frequency", "monetary",
              "r_score", "f_score", "m_score", "segment"]]
    with engine.begin() as conn:
        # recalcul complet à chaque exécution : on vide avant de réécrire
        conn.execute(text("TRUNCATE analytics.rfm_segments"))
        out.to_sql("rfm_segments", conn, schema="analytics",
                   if_exists="append", index=False, chunksize=10_000)
    log.info("%d clients écrits dans analytics.rfm_segments", len(out))

if __name__ == "__main__":
    main()
