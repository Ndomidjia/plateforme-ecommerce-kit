"""Mon registre de versions de modèles : je décide si une nouvelle exécution
doit remplacer ("promouvoir") le modèle actif en production, et je conserve
un point de retour en arrière (rollback) d'un niveau.

Contexte (retour de soutenance) : avant ce module, mon recalcul à la demande
(cf. api/routers/admin.py) écrasait toujours churn_scores / customer_360 en
place (TRUNCATE + réécriture), sans comparaison avec le modèle en place ni
possibilité de revenir en arrière -- un modèle moins bon pouvait remplacer
silencieusement un meilleur. J'ai écrit ce module pour fermer ce trou :
1. je ne promeus la nouvelle version que si elle n'est pas significativement
   moins bonne que la version active (tolérance PROMOTION_TOLERANCE) ;
2. si je la rejette, je ne touche pas aux tables live -- j'écris quand même
   le résultat du run rejeté dans une table `_candidate`, pour inspection,
   plutôt que de le jeter silencieusement ;
3. avant chaque promotion, je sauvegarde l'état sortant dans une table
   `_previous`, ce qui permet un rollback d'un niveau via mon API admin.

Pourquoi j'ai choisi un rollback à un niveau plutôt qu'un historique complet
versionné (type MLflow) : proportionné à l'échelle de mon projet -- voir
sql/11_model_registry.sql.
"""
import logging
from sqlalchemy import text

log = logging.getLogger("analytics.model_registry")

# Je ne promeus une nouvelle version que si sa métrique n'est pas inférieure
# de plus de ce seuil à celle de la version active. Ça tolère le bruit
# naturel d'un ré-entraînement (même config, même données -> métrique
# légèrement différente à chaque run à cause de l'aléatoire résiduel), sans
# laisser passer une vraie régression.
PROMOTION_TOLERANCE = 0.01


def get_active(engine, model_name: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT model_name, active_version, active_metric, has_backup, "
                "previous_version, previous_metric FROM analytics.model_registry "
                "WHERE model_name = :m"
            ),
            {"m": model_name},
        ).mappings().first()
    if row is None:
        return None
    # NUMERIC -> decimal.Decimal via psycopg2 : je reconvertis en float pour
    # rester arithmétiquement compatible avec mes métriques sklearn (float).
    result = dict(row)
    if result.get("active_metric") is not None:
        result["active_metric"] = float(result["active_metric"])
    if result.get("previous_metric") is not None:
        result["previous_metric"] = float(result["previous_metric"])
    return result


def decide_promotion(engine, model_name: str, new_metric: float) -> dict:
    """Retourne {'promote': bool, 'reason': str, 'active_before': dict|None}."""
    active = get_active(engine, model_name)
    if active is None or active["active_metric"] is None:
        return {"promote": True, "reason": "aucune version active en production (premier déploiement)", "active_before": active}

    threshold = active["active_metric"] - PROMOTION_TOLERANCE
    if new_metric >= threshold:
        return {
            "promote": True,
            "reason": f"{new_metric:.4f} >= {active['active_metric']:.4f} - {PROMOTION_TOLERANCE} (pas de régression significative)",
            "active_before": active,
        }
    return {
        "promote": False,
        "reason": f"{new_metric:.4f} < {active['active_metric']:.4f} - {PROMOTION_TOLERANCE} (régression détectée)",
        "active_before": active,
    }


def _table_exists(conn, schema_qualified_name: str) -> bool:
    return conn.execute(text("SELECT to_regclass(:t)"), {"t": schema_qualified_name}).scalar() is not None


def _ensure_shadow_table(conn, table: str, suffix: str):
    shadow = f"{table}_{suffix}"
    if not _table_exists(conn, f"analytics.{shadow}"):
        conn.execute(text(f"CREATE TABLE analytics.{shadow} (LIKE analytics.{table} INCLUDING ALL)"))
    return shadow


def snapshot_before_promotion(engine, tables: list[str]):
    """J'appelle ça juste AVANT de tronquer/réécrire les tables live --
    uniquement si decide_promotion() a répondu promote=True. J'écrase le
    snapshot précédent (rollback à un seul niveau, voir docstring du
    module)."""
    with engine.begin() as conn:
        for t in tables:
            shadow = _ensure_shadow_table(conn, t, "previous")
            conn.execute(text(f"TRUNCATE analytics.{shadow}"))
            conn.execute(text(f"INSERT INTO analytics.{shadow} SELECT * FROM analytics.{t}"))
    log.info("Sauvegarde de rollback créée pour : %s", ", ".join(tables))


def write_rejected_candidate(engine, table: str, df):
    """J'écris le résultat d'une version rejetée dans `<table>_candidate`,
    pour inspection, SANS toucher à la table live (qui continue de servir
    l'ancienne version, active)."""
    with engine.begin() as conn:
        shadow = _ensure_shadow_table(conn, table, "candidate")
        conn.execute(text(f"TRUNCATE analytics.{shadow}"))
        df.to_sql(shadow, conn, schema="analytics", if_exists="append", index=False, chunksize=5_000)
    log.info("Résultat rejeté écrit dans analytics.%s_candidate (non servi, table live inchangée)", table)


def promote(engine, model_name: str, version: str, metric_value: float, decision: dict):
    active = decision["active_before"]
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO analytics.model_registry
                    (model_name, active_version, active_metric, has_backup, previous_version, previous_metric, promoted_at)
                VALUES (:m, :v, :metric, :has_backup, :pv, :pm, NOW())
                ON CONFLICT (model_name) DO UPDATE SET
                    active_version = EXCLUDED.active_version,
                    active_metric = EXCLUDED.active_metric,
                    has_backup = EXCLUDED.has_backup,
                    previous_version = EXCLUDED.previous_version,
                    previous_metric = EXCLUDED.previous_metric,
                    promoted_at = EXCLUDED.promoted_at
                """
            ),
            {
                "m": model_name,
                "v": version,
                "metric": metric_value,
                "has_backup": active is not None,
                "pv": active["active_version"] if active else None,
                "pm": active["active_metric"] if active else None,
            },
        )
    log.info(
        "Modèle '%s' promu : version=%s metric=%.4f (précédente : %s)",
        model_name, version, metric_value,
        active["active_version"] if active else "aucune (premier déploiement)",
    )
