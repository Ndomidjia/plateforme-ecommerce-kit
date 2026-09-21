"""ETL Retailrocket : CSV bruts -> schéma PostgreSQL 'retailrocket'."""
import logging
import pandas as pd
from config import get_engine, RAW_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("etl.retailrocket")

SRC = RAW_DIR / "retailrocket"

def load_events(engine):
    df = pd.read_csv(SRC / "events.csv")
    # timestamp epoch millisecondes -> datetime
    df["event_time"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.rename(columns={"visitorid": "visitor_id", "event": "event_type",
                            "itemid": "item_id", "transactionid": "transaction_id"})
    df = df[["event_time", "visitor_id", "event_type", "item_id", "transaction_id"]]
    df.to_sql("events", engine, schema="retailrocket",
              if_exists="append", index=False, chunksize=50_000)
    log.info("events : %d lignes chargées", len(df))

def load_item_properties(engine):
    for part in ["item_properties_part1.csv", "item_properties_part2.csv"]:
        df = pd.read_csv(SRC / part)
        df["property_time"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.rename(columns={"itemid": "item_id"})
        df = df[["property_time", "item_id", "property", "value"]]
        df.to_sql("item_properties", engine, schema="retailrocket",
                  if_exists="append", index=False, chunksize=50_000)
        log.info("%s : %d lignes chargées", part, len(df))

def load_category_tree(engine):
    df = pd.read_csv(SRC / "category_tree.csv")
    df = df.rename(columns={"categoryid": "category_id", "parentid": "parent_id"})
    df.to_sql("category_tree", engine, schema="retailrocket",
              if_exists="append", index=False)
    log.info("category_tree : %d lignes chargées", len(df))

def main():
    engine = get_engine()
    load_events(engine)
    load_item_properties(engine)
    load_category_tree(engine)

if __name__ == "__main__":
    main()
