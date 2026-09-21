-- Vue client 360° unifiée sur Olist : combine RFM, proxy de risque de
-- non-réachat (PAS un vrai churn, voir docs/limitations-methodologiques.md),
-- sentiment moyen des avis et recommandation de catégorie.
-- C'est la réponse à la remarque de l'encadrant : "fusionner les données"
-- se fait ici au niveau des RÉSULTATS d'analyse sur une même population
-- (les clients Olist), pas au niveau des lignes brutes des 3 datasets
-- (impossible : aucun identifiant commun entre Olist/Retailrocket/churn).

CREATE TABLE IF NOT EXISTS analytics.customer_360 (
    customer_unique_id         VARCHAR(50) PRIMARY KEY,

    -- RFM (dupliqué depuis analytics.rfm_segments pour lecture en une requête)
    rfm_segment                VARCHAR(50),
    recency_days               INT,
    frequency                  INT,
    monetary                   NUMERIC(12,2),

    -- Proxy de risque de non-réachat (pas un vrai churn)
    repurchase_threshold_days  INT NOT NULL,
    is_censored                BOOLEAN NOT NULL,   -- TRUE si pas assez de recul pour connaître l'issue réelle
    proxy_risk_proba           NUMERIC(6,4),
    proxy_risk_level           VARCHAR(10),        -- low | medium | high

    -- Sentiment (moyenne des avis du client, cf analytics.review_sentiment)
    avg_review_score           NUMERIC(4,2),
    dominant_sentiment         VARCHAR(10),

    -- Recommandation (dérivée de analytics.association_rules, uniquement si lift >= 1)
    top_category                 VARCHAR(100),
    recommended_category         VARCHAR(100),
    recommended_category_lift    NUMERIC(10,4),

    model_version               VARCHAR(50) NOT NULL,
    computed_at                 TIMESTAMP DEFAULT NOW()
);
