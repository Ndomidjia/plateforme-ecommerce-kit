"""ETL Churn : CSV des profils clients -> schéma PostgreSQL 'churn'."""
import logging
import pandas as pd
from config import get_engine, RAW_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("etl.churn")

SRC = RAW_DIR / "churn" / "ecommerce_customer_churn_dataset.csv"

def main():
    engine = get_engine()
    df = pd.read_csv(SRC)
    n_raw = len(df)

    # noms de colonnes CSV -> noms de colonnes SQL (snake_case)
    df.columns = [c.lower() for c in df.columns]

    # -- Transformations --
    df = df.drop_duplicates()
    # TODO : stratégie d'imputation des valeurs manquantes, à documenter
    # dans le mémoire (ex. médiane par segment). Pour l'instant : laissées
    # en NULL, l'imputation se fera côté module ML (pipeline scikit-learn).

    df.to_sql("customer_profiles", engine, schema="churn",
              if_exists="append", index=False, chunksize=10_000)
    log.info("churn.customer_profiles : %d lignes lues, %d chargées", n_raw, len(df))

if __name__ == "__main__":
    main()
