-- Résultats de l'analyse de sentiment (deep learning) sur les avis Olist.
-- Rattachée à analytics (zone de convergence), comme les autres résultats ML.

CREATE TABLE IF NOT EXISTS analytics.review_sentiment (
    review_id       VARCHAR(50) NOT NULL,
    order_id        VARCHAR(50) NOT NULL,
    review_score    INT,                 -- note d'origine (1-5), conservée pour comparaison
    sentiment       VARCHAR(10) NOT NULL CHECK (sentiment IN ('negative', 'neutral', 'positive')),
    sentiment_proba NUMERIC(6,4),        -- confiance du modèle sur la classe prédite
    computed_at     TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (review_id, order_id),
    FOREIGN KEY (review_id, order_id) REFERENCES olist.order_reviews(review_id, order_id)
);
