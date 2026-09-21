-- Plan A : 3 sources séparées + 1 zone analytique de convergence
CREATE SCHEMA IF NOT EXISTS olist;         -- transactionnel (9 tables)
CREATE SCHEMA IF NOT EXISTS retailrocket;  -- comportemental (clickstream)
CREATE SCHEMA IF NOT EXISTS churn;         -- profils clients labellisés
CREATE SCHEMA IF NOT EXISTS analytics;     -- résultats des modules ML
