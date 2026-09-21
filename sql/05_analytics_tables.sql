-- Schéma ANALYTICS : point de convergence — résultats des modules ML
-- Rempli par les scripts d'analyse, consommé par l'API/dashboard.

CREATE TABLE IF NOT EXISTS analytics.rfm_segments (
    customer_unique_id VARCHAR(50) PRIMARY KEY,
    recency_days       INT,
    frequency          INT,
    monetary           NUMERIC(12,2),
    r_score            SMALLINT,
    f_score            SMALLINT,
    m_score            SMALLINT,
    segment            VARCHAR(50),      -- ex: 'Champions', 'A risque', ...
    computed_at        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics.association_rules (
    rule_id      SERIAL PRIMARY KEY,
    antecedents  TEXT NOT NULL,          -- catégories/produits déclencheurs
    consequents  TEXT NOT NULL,          -- catégories/produits recommandés
    support      NUMERIC(8,6),
    confidence   NUMERIC(8,6),
    lift         NUMERIC(10,4),
    computed_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics.funnel_stats (
    period_start  DATE,
    period_end    DATE,
    views         BIGINT,
    addtocarts    BIGINT,
    transactions  BIGINT,
    view_to_cart_rate NUMERIC(6,4),
    cart_to_buy_rate  NUMERIC(6,4),
    computed_at   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics.item_recommendations (
    item_id            BIGINT,
    recommended_item_id BIGINT,
    score              NUMERIC(10,6),
    method             VARCHAR(50),     -- 'item-item CF', 'popularity', ...
    computed_at        TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (item_id, recommended_item_id, method)
);

CREATE TABLE IF NOT EXISTS analytics.churn_scores (
    customer_id   INT REFERENCES churn.customer_profiles(customer_id),
    churn_proba   NUMERIC(6,4) NOT NULL,
    risk_level    VARCHAR(10),           -- low | medium | high
    model_version VARCHAR(50),
    scored_at     TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (customer_id, model_version)
);
