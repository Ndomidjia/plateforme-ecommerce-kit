"""Funnel de conversion Retailrocket : view -> addtocart -> transaction.

Compte les VISITEURS DISTINCTS ayant atteint chaque étape (pas les
événements bruts) : un visiteur qui consulte 10 fois le même produit sans
jamais l'ajouter au panier ne doit pas gonfler artificiellement le taux de
vue. C'est la définition standard d'un taux de conversion funnel.

Découpage hebdomadaire (dataset ~4,5 mois -> ~20 semaines) + une ligne de
synthèse sur toute la période.
"""
import logging
import pandas as pd
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analytics.funnel_retailrocket")

WEEKLY_QUERY = """
SELECT
    date_trunc('week', event_time)::date AS period_start,
    event_type,
    COUNT(DISTINCT visitor_id) AS visitors
FROM retailrocket.events
GROUP BY period_start, event_type
"""

GLOBAL_QUERY = """
SELECT
    MIN(event_time)::date AS period_start,
    MAX(event_time)::date AS period_end,
    COUNT(DISTINCT visitor_id) FILTER (WHERE event_type = 'view')        AS views,
    COUNT(DISTINCT visitor_id) FILTER (WHERE event_type = 'addtocart')   AS addtocarts,
    COUNT(DISTINCT visitor_id) FILTER (WHERE event_type = 'transaction') AS transactions
FROM retailrocket.events
"""

def add_rates(df: pd.DataFrame) -> pd.DataFrame:
    df["view_to_cart_rate"] = (df["addtocarts"] / df["views"]).where(df["views"] > 0)
    df["cart_to_buy_rate"] = (df["transactions"] / df["addtocarts"]).where(df["addtocarts"] > 0)
    return df

def build_weekly(engine) -> pd.DataFrame:
    long_df = pd.read_sql(WEEKLY_QUERY, engine, parse_dates=["period_start"])
    wide = long_df.pivot(index="period_start", columns="event_type", values="visitors").fillna(0)
    wide = wide.rename(columns={"view": "views", "addtocart": "addtocarts", "transaction": "transactions"})
    for col in ("views", "addtocarts", "transactions"):
        if col not in wide.columns:
            wide[col] = 0
    wide = wide.reset_index()
    wide["period_end"] = wide["period_start"] + pd.Timedelta(days=6)
    return add_rates(wide)

def build_global(engine) -> pd.DataFrame:
    df = pd.read_sql(GLOBAL_QUERY, engine, parse_dates=["period_start", "period_end"])
    return add_rates(df)

def main():
    # Import local, voir commentaire équivalent dans rfm_olist.py.
    from config import get_engine

    engine = get_engine()
    weekly = build_weekly(engine)
    glob = build_global(engine)
    log.info("%d semaines calculées + 1 ligne globale", len(weekly))

    cols = ["period_start", "period_end", "views", "addtocarts", "transactions",
            "view_to_cart_rate", "cart_to_buy_rate"]
    out = pd.concat([weekly[cols], glob[cols]], ignore_index=True)

    with pd.option_context("display.width", 140):
        print(out.to_string(index=False))

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE analytics.funnel_stats"))
        out.to_sql("funnel_stats", conn, schema="analytics",
                   if_exists="append", index=False)
    log.info("%d lignes écrites dans analytics.funnel_stats", len(out))

if __name__ == "__main__":
    main()
