-- Contrôles qualité post-ETL : volumes attendus par table
SELECT 'olist.orders' AS t, COUNT(*) FROM olist.orders
UNION ALL SELECT 'olist.order_items', COUNT(*) FROM olist.order_items
UNION ALL SELECT 'olist.customers', COUNT(*) FROM olist.customers
UNION ALL SELECT 'retailrocket.events', COUNT(*) FROM retailrocket.events
UNION ALL SELECT 'churn.customer_profiles', COUNT(*) FROM churn.customer_profiles;

-- Intégrité : commandes sans client (doit retourner 0)
SELECT COUNT(*) AS commandes_orphelines
FROM olist.orders o LEFT JOIN olist.customers c USING (customer_id)
WHERE c.customer_id IS NULL;
