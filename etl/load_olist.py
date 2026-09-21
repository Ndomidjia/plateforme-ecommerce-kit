"""ETL Olist : CSV bruts -> schéma PostgreSQL 'olist'.
Patron Extract / Transform / Load, journalisé.
"""
import logging
import pandas as pd
from config import get_engine, RAW_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("etl.olist")

SRC = RAW_DIR / "olist"

# fichier CSV -> (table cible, colonnes dates à parser)
FILES = {
    "olist_customers_dataset.csv":  ("customers", []),
    "olist_sellers_dataset.csv":    ("sellers", []),
    "olist_products_dataset.csv":   ("products", []),
    "olist_orders_dataset.csv":     ("orders", [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date"]),
    "olist_order_items_dataset.csv":    ("order_items", ["shipping_limit_date"]),
    "olist_order_payments_dataset.csv": ("order_payments", []),
    "olist_order_reviews_dataset.csv":  ("order_reviews", [
        "review_creation_date", "review_answer_timestamp"]),
    "olist_geolocation_dataset.csv":    ("geolocation", []),
    "product_category_name_translation.csv": ("category_translation", []),
}

def transform(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Nettoyages communs + spécifiques par table."""
    if table == "order_reviews":
        # doublons (review_id, order_id) présents dans le CSV brut
        df = df.drop_duplicates(subset=["review_id", "order_id"])
    if table == "geolocation":
        df = df.drop_duplicates()
    # TODO : ajouter ici vos contrôles qualité (valeurs aberrantes, etc.)
    return df

def main():
    engine = get_engine()
    # Ordre d'insertion = respect des clés étrangères
    for fname, (table, date_cols) in FILES.items():
        path = SRC / fname
        if not path.exists():
            log.warning("Fichier absent, ignoré : %s", path)
            continue
        df = pd.read_csv(path, parse_dates=date_cols)          # Extract
        n_raw = len(df)
        df = transform(df, table)                              # Transform
        df.to_sql(table, engine, schema="olist",               # Load
                  if_exists="append", index=False, chunksize=10_000)
        log.info("%s -> olist.%s : %d lignes lues, %d chargées",
                 fname, table, n_raw, len(df))

if __name__ == "__main__":
    main()
