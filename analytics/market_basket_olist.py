"""Market basket analysis (règles d'association) sur Olist.

Étape 1 : construction des transactions et calcul des itemsets fréquents.
Analyse au niveau CATÉGORIE de produit (product_category_name_english), pas
produit individuel : avec 32 951 produits pour seulement 3 197 commandes
multi-produits, le niveau produit ne donnerait aucun support exploitable.
Au niveau catégorie (71 valeurs), 723 commandes livrées contiennent 2+
catégories distinctes — c'est notre gisement de règles.

L'univers des transactions reste TOUTES les commandes livrées (pas
seulement les multi-catégories) : le support d'une règle se calcule sur
l'ensemble des commandes, sinon on le surestimerait.
"""
import logging
import pandas as pd
from sqlalchemy import text
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules
from config import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analytics.market_basket_olist")

QUERY = """
SELECT
    o.order_id,
    COALESCE(ct.product_category_name_english, p.product_category_name) AS category
FROM olist.orders o
JOIN olist.order_items oi ON oi.order_id = o.order_id
JOIN olist.products p ON p.product_id = oi.product_id
LEFT JOIN olist.category_translation ct ON ct.product_category_name = p.product_category_name
WHERE o.order_status = 'delivered'
"""

def build_transactions(engine) -> list[set]:
    df = pd.read_sql(QUERY, engine)
    n_before = df["order_id"].nunique()
    df = df.dropna(subset=["category"])  # catégorie produit manquante : commande ignorable pour cette analyse
    n_after = df["order_id"].nunique()
    log.info("%d commandes livrées, %d avec catégorie connue", n_before, n_after)
    return df.groupby("order_id")["category"].apply(set).tolist()

def main():
    engine = get_engine()
    transactions = build_transactions(engine)

    te = TransactionEncoder()
    te_ary = te.fit(transactions).transform(transactions)
    basket_df = pd.DataFrame(te_ary, columns=te.columns_)
    log.info("%d transactions encodées, %d catégories distinctes", *basket_df.shape)

    # seuil bas volontairement : max théorique de support pour une paire de
    # catégories = 723/96478 ≈ 0.0075 (voir docstring). On affine après coup.
    freq_itemsets = apriori(basket_df, min_support=0.00008, use_colnames=True)
    log.info("Itemsets fréquents trouvés : %d", len(freq_itemsets))

    # Pas de filtre sur le lift ici : on écrit toutes les règles générées à
    # partir des itemsets de taille >= 2, lift compris. Une seule paire sur
    # 18 dépasse lift=1 sur Olist (voir docstring) — c'est un résultat en soi,
    # pas une raison de tronquer la table. Le filtrage "règles fortes" se
    # fait en aval (API/dashboard) via la colonne lift.
    rules = association_rules(freq_itemsets, metric="confidence", min_threshold=0.0)
    rules = rules.sort_values("lift", ascending=False)
    log.info("%d règles générées", len(rules))

    out = pd.DataFrame({
        "antecedents": rules["antecedents"].apply(lambda s: ", ".join(sorted(s))),
        "consequents": rules["consequents"].apply(lambda s: ", ".join(sorted(s))),
        "support": rules["support"],
        "confidence": rules["confidence"],
        "lift": rules["lift"],
    })

    with pd.option_context("display.width", 140):
        print(out.to_string(index=False))

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE analytics.association_rules RESTART IDENTITY"))
        out.to_sql("association_rules", conn, schema="analytics",
                   if_exists="append", index=False)
    log.info("%d règles écrites dans analytics.association_rules", len(out))

if __name__ == "__main__":
    main()
