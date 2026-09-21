-- Importance des variables du modèle churn (déjà calculée dans churn_model.py,
-- jamais persistée jusqu'ici) : utile pour l'expliquer côté dashboard admin.

CREATE TABLE IF NOT EXISTS analytics.churn_feature_importance (
    feature       VARCHAR(100) NOT NULL,
    importance    NUMERIC(8,6) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    computed_at   TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (feature, model_version)
);
