"""Modèle de scoring churn sur churn.customer_profiles.

Étape 1 : comparaison Régression Logistique vs Random Forest sur un split
train/test, avant de choisir le modèle final et de scorer toute la base.
"""
import logging
from datetime import datetime

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, classification_report, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import text
from config import get_engine
import model_registry

MODEL_NAME = "churn_scoring"
# Versionné par horodatage (un run = une version distincte) plutôt qu'une
# constante fixe : nécessaire pour que model_registry puisse distinguer
# une nouvelle exécution de la version actuellement en production, et pour
# que le rollback ait un "avant" et un "après" identifiables.
MODEL_VERSION = f"random_forest_{datetime.now():%Y%m%d_%H%M%S}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analytics.churn_model")

NUMERIC_FEATURES = [
    "age", "membership_years", "login_frequency", "session_duration_avg",
    "pages_per_session", "cart_abandonment_rate", "wishlist_items",
    "total_purchases", "average_order_value", "days_since_last_purchase",
    "discount_usage_rate", "returns_rate", "email_open_rate",
    "customer_service_calls", "product_reviews_written",
    "social_media_engagement_score", "mobile_app_usage",
    "payment_method_diversity", "lifetime_value", "credit_balance",
]
CATEGORICAL_FEATURES = ["gender", "country", "city", "signup_quarter"]
TARGET = "churned"

def load_data(engine) -> pd.DataFrame:
    cols = ["customer_id"] + NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET]
    df = pd.read_sql(f"SELECT {', '.join(cols)} FROM churn.customer_profiles", engine)
    log.info("%d clients chargés", len(df))
    return df

def build_preprocessor() -> ColumnTransformer:
    numeric_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    return ColumnTransformer([
        ("num", numeric_pipe, NUMERIC_FEATURES),
        ("cat", categorical_pipe, CATEGORICAL_FEATURES),
    ])

def evaluate(name, pipeline, X_test, y_test):
    proba = pipeline.predict_proba(X_test)[:, 1]
    pred = pipeline.predict(X_test)
    roc_auc = roc_auc_score(y_test, proba)
    pr_auc = average_precision_score(y_test, proba)
    log.info("=== %s === ROC-AUC=%.4f  PR-AUC=%.4f", name, roc_auc, pr_auc)
    print(classification_report(y_test, pred, target_names=["actif", "churn"]))
    return roc_auc, pr_auc

def log_metrics_history(engine, metrics: dict):
    """Écrit dans analytics.model_metrics_history (append-only, jamais vidé,
    contrairement à analytics.churn_scores) -- fondation pour un futur suivi
    de dérive dans le temps."""
    rows = pd.DataFrame([
        {"model_name": MODEL_NAME, "model_version": MODEL_VERSION, "metric_name": k, "metric_value": v}
        for k, v in metrics.items()
    ])
    rows.to_sql("model_metrics_history", engine, schema="analytics", if_exists="append", index=False)
    log.info("%d métriques journalisées dans analytics.model_metrics_history", len(rows))

def main():
    engine = get_engine()
    df = load_data(engine)
    metrics_to_log = {"pct_positive_class": float(df[TARGET].mean())}

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42)

    models = {
        "logistic_regression": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "random_forest": RandomForestClassifier(
            n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1),
    }

    for name, model in models.items():
        pipeline = Pipeline([("prep", build_preprocessor()), ("model", model)])
        pipeline.fit(X_train, y_train)
        roc_auc, pr_auc = evaluate(name, pipeline, X_test, y_test)
        metrics_to_log[f"test_roc_auc__{name}"] = roc_auc
        metrics_to_log[f"test_pr_auc__{name}"] = pr_auc

        if name == "random_forest":
            feature_names = pipeline.named_steps["prep"].get_feature_names_out()
            importances = pd.Series(model.feature_importances_, index=feature_names)
            print("\nTop 15 variables les plus importantes (Random Forest) :")
            print(importances.sort_values(ascending=False).head(15).to_string())

    # Modèle retenu (voir comparaison ci-dessus) : Random Forest.
    # Scoring par validation croisée (5 plis) plutôt que sur un modèle
    # entraîné puis réappliqué aux mêmes données : un Random Forest de 300
    # arbres mémorise quasiment le train set, donc predict_proba "in-sample"
    # donnerait des probabilités artificiellement extrêmes (proches de 0/1).
    # Avec cross_val_predict, chaque client est scoré par un modèle qui ne
    # l'a pas vu à l'entraînement -> scores honnêtes, cohérents avec l'AUC
    # mesuré sur le test set, tout en couvrant 100% de la base.
    final_model = RandomForestClassifier(
        n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1)
    final_pipeline = Pipeline([("prep", build_preprocessor()), ("model", final_model)])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    proba_matrix = cross_val_predict(final_pipeline, X, y, cv=cv, method="predict_proba", n_jobs=-1)
    churn_proba = proba_matrix[:, 1]
    metrics_to_log["oof_roc_auc"] = roc_auc_score(y, churn_proba)

    risk_level = pd.cut(churn_proba, bins=[-0.01, 0.3, 0.6, 1.01],
                        labels=["low", "medium", "high"])

    scores = pd.DataFrame({
        "customer_id": df["customer_id"],
        "churn_proba": churn_proba,
        "risk_level": risk_level.astype(str),
        "model_version": MODEL_VERSION,
    })
    log.info("Répartition des niveaux de risque :\n%s",
             scores["risk_level"].value_counts().to_string())

    # Importance des variables : nécessite un modèle réellement entraîné
    # (cross_val_predict clone l'estimateur en interne à chaque pli, il ne
    # laisse pas de modèle final entraîné). Pas de fuite de données ici :
    # contrairement aux probabilités par client, l'importance est une mesure
    # globale de la structure apprise, pas une prédiction individuelle.
    final_pipeline.fit(X, y)
    feature_names = final_pipeline.named_steps["prep"].get_feature_names_out()
    importance = pd.DataFrame({
        "feature": feature_names,
        "importance": final_pipeline.named_steps["model"].feature_importances_,
        "model_version": MODEL_VERSION,
    })

    # Décision de promotion : une nouvelle version n'écrase les tables live
    # (donc ce que sert l'API) que si elle n'est pas significativement moins
    # bonne que la version actuellement en production. Sinon, ses résultats
    # sont conservés pour inspection (churn_scores_candidate /
    # churn_feature_importance_candidate) mais la version active continue de
    # servir. Voir analytics/model_registry.py.
    decision = model_registry.decide_promotion(engine, MODEL_NAME, metrics_to_log["oof_roc_auc"])
    metrics_to_log["promoted"] = 1.0 if decision["promote"] else 0.0
    log.info("Décision de promotion (%s) : %s", MODEL_VERSION, decision["reason"])

    if decision["promote"]:
        model_registry.snapshot_before_promotion(engine, ["churn_scores", "churn_feature_importance"])
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE analytics.churn_scores"))
            scores.to_sql("churn_scores", conn, schema="analytics",
                          if_exists="append", index=False, chunksize=10_000)
            conn.execute(text("TRUNCATE analytics.churn_feature_importance"))
            importance.to_sql("churn_feature_importance", conn, schema="analytics",
                              if_exists="append", index=False)
        model_registry.promote(engine, MODEL_NAME, MODEL_VERSION, metrics_to_log["oof_roc_auc"], decision)
        log.info("%d clients scorés et écrits dans analytics.churn_scores (version active : %s)",
                 len(scores), MODEL_VERSION)
    else:
        model_registry.write_rejected_candidate(engine, "churn_scores", scores)
        model_registry.write_rejected_candidate(engine, "churn_feature_importance", importance)
        log.warning(
            "Nouvelle version '%s' NON promue (%s) -- la version précédente reste active en "
            "production. Résultats disponibles pour inspection dans analytics.churn_scores_candidate.",
            MODEL_VERSION, decision["reason"],
        )

    log_metrics_history(engine, metrics_to_log)

if __name__ == "__main__":
    main()
