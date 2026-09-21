-- Historique des métriques de modèle (append-only, jamais vidé) : fondation
-- pour le monitoring de drift prévu au plan initial. Les tables analytics.*
-- existantes sont toutes en TRUNCATE + réécriture à chaque recalcul, donc
-- ne conservent aucun historique -- celle-ci comble ce manque en gardant
-- une ligne par métrique à chaque exécution d'un script.

CREATE TABLE IF NOT EXISTS analytics.model_metrics_history (
    id            SERIAL PRIMARY KEY,
    model_name    VARCHAR(50) NOT NULL,   -- ex: 'churn_scoring', 'customer_360_proxy'
    model_version VARCHAR(50) NOT NULL,
    metric_name   VARCHAR(50) NOT NULL,   -- ex: 'roc_auc', 'pr_auc', 'pct_positive_class'
    metric_value  NUMERIC(12,6) NOT NULL,
    computed_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_metrics_history_model ON analytics.model_metrics_history(model_name, computed_at);
