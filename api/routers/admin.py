"""Endpoints réservés aux admins : KPIs d'administration (comptes API,
activité RGPD, métadonnées du modèle de churn) et recalcul à la demande des
modules ML. Distinct de /rgpd (qui manipule des données personnelles) : ici,
uniquement des métadonnées système et des actions opérationnelles.
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection

from database import get_db
from deps import require_role

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("admin"))])

ANALYTICS_DIR = Path(__file__).resolve().parent.parent.parent / "analytics"

MODULE_SCRIPTS = {
    "rfm": "rfm_olist.py",
    "market_basket": "market_basket_olist.py",
    "funnel": "funnel_retailrocket.py",
    "recommendations": "recommend_retailrocket.py",
    "churn": "churn_model.py",
    "sentiment": "sentiment_olist.py",
    "customer_360": "customer_360_olist.py",  # dépend de rfm/sentiment/market_basket : à lancer après eux
}

# État des recalculs en mémoire (process, horodatages) : suffisant pour une
# API mono-processus comme ici (un seul worker uvicorn). Ne survit pas à un
# redémarrage de l'API et ne fonctionnerait pas avec plusieurs workers -- une
# vraie file de tâches (Celery/RQ) serait nécessaire en production.
_jobs: dict[str, dict] = {}

class UserRoleCount(BaseModel):
    role: str
    count: int

class RgpdAuditEntry(BaseModel):
    action: str
    schema_name: str
    subject_id: str
    requested_by: str
    requested_at: str

class AdminOverview(BaseModel):
    users_by_role: list[UserRoleCount]
    rgpd_total_actions: int
    rgpd_recent: list[RgpdAuditEntry]
    churn_model_version: Optional[str]
    churn_model_scored_at: Optional[str]

@router.get("/overview", response_model=AdminOverview)
def get_admin_overview(db: Connection = Depends(get_db)):
    users_by_role = db.execute(
        text("SELECT role, COUNT(*) AS count FROM app.users GROUP BY role")
    ).mappings().all()

    rgpd_total = db.execute(text("SELECT COUNT(*) FROM app.rgpd_audit_log")).scalar()

    rgpd_recent = db.execute(
        text("SELECT action, schema_name, subject_id, requested_by, requested_at::text "
             "FROM app.rgpd_audit_log ORDER BY requested_at DESC LIMIT 5")
    ).mappings().all()

    model_row = db.execute(
        text("SELECT model_version, MAX(scored_at)::text AS scored_at "
             "FROM analytics.churn_scores GROUP BY model_version "
             "ORDER BY MAX(scored_at) DESC LIMIT 1")
    ).mappings().first()

    return AdminOverview(
        users_by_role=users_by_role,
        rgpd_total_actions=rgpd_total,
        rgpd_recent=rgpd_recent,
        churn_model_version=model_row["model_version"] if model_row else None,
        churn_model_scored_at=model_row["scored_at"] if model_row else None,
    )

class RecomputeStatus(BaseModel):
    module: str
    status: str  # running | success | failed | never_run
    started_at: Optional[str]
    finished_at: Optional[str]

@router.get("/recompute/status", response_model=list[RecomputeStatus])
def get_recompute_status():
    result = []
    for module in MODULE_SCRIPTS:
        job = _jobs.get(module)
        if job is None:
            result.append(RecomputeStatus(module=module, status="never_run", started_at=None, finished_at=None))
            continue

        exit_code = job["process"].poll()
        if exit_code is not None and job["finished_at"] is None:
            job["finished_at"] = datetime.now()
            job["exit_code"] = exit_code

        if exit_code is None:
            status_value = "running"
        else:
            status_value = "success" if exit_code == 0 else "failed"

        result.append(RecomputeStatus(
            module=module,
            status=status_value,
            started_at=job["started_at"].isoformat(),
            finished_at=job["finished_at"].isoformat() if job["finished_at"] else None,
        ))
    return result

@router.post("/recompute/{module}", response_model=RecomputeStatus, status_code=202)
def trigger_recompute(module: str):
    if module not in MODULE_SCRIPTS:
        raise HTTPException(status_code=404, detail=f"Module inconnu. Valeurs possibles : {list(MODULE_SCRIPTS)}")

    existing = _jobs.get(module)
    if existing and existing["process"].poll() is None:
        raise HTTPException(status_code=409, detail=f"Un recalcul de '{module}' est déjà en cours")

    script = ANALYTICS_DIR / MODULE_SCRIPTS[module]
    process = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=str(ANALYTICS_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    started_at = datetime.now()
    _jobs[module] = {"process": process, "started_at": started_at, "finished_at": None, "exit_code": None}
    return RecomputeStatus(module=module, status="running", started_at=started_at.isoformat(), finished_at=None)


# ---------------------------------------------------------------------------
# Registre de versions de modèles (voir analytics/model_registry.py) :
# quelle version est active en production pour chaque modèle entraîné, et
# retour en arrière (rollback) d'un niveau si un recalcul a promu une version
# qui se révèle problématique malgré le contrôle automatique à la promotion.
# ---------------------------------------------------------------------------

# Tables live à restaurer depuis leur sauvegarde (<table>_previous) lors d'un
# rollback, par modèle -- dupliqué depuis les scripts analytics/ plutôt que
# partagé : ces scripts et l'API tournent dans deux répertoires/process
# distincts (voir analytics/config.py vs api/config.py), un import partagé
# n'apporterait pas grand-chose pour 2 lignes de mapping statique.
MODEL_LIVE_TABLES = {
    "churn_scoring": ["churn_scores", "churn_feature_importance"],
    "customer_360_proxy": ["customer_360"],
}

class ModelRegistryEntry(BaseModel):
    model_name: str
    active_version: str
    active_metric: Optional[float]
    has_backup: bool
    previous_version: Optional[str]
    previous_metric: Optional[float]
    promoted_at: str

_REGISTRY_COLUMNS = (
    "model_name, active_version, active_metric, has_backup, "
    "previous_version, previous_metric, promoted_at::text"
)

@router.get("/models", response_model=list[ModelRegistryEntry])
def list_model_registry(db: Connection = Depends(get_db)):
    rows = db.execute(
        text(f"SELECT {_REGISTRY_COLUMNS} FROM analytics.model_registry ORDER BY model_name")
    ).mappings().all()
    return rows

@router.post("/models/{model_name}/rollback", response_model=ModelRegistryEntry)
def rollback_model(model_name: str, db: Connection = Depends(get_db)):
    """Restaure, pour ce modèle, l'état des tables live sauvegardé lors de la
    DERNIÈRE promotion (un seul niveau de rollback -- voir
    analytics/model_registry.py pour la justification). Le résultat écrasé
    par le rollback est conservé dans `<table>_candidate` pour inspection,
    comme pour une version rejetée automatiquement."""
    if model_name not in MODEL_LIVE_TABLES:
        raise HTTPException(status_code=404, detail=f"Modèle inconnu. Valeurs possibles : {list(MODEL_LIVE_TABLES)}")

    row = db.execute(
        text(f"SELECT {_REGISTRY_COLUMNS} FROM analytics.model_registry WHERE model_name = :m"),
        {"m": model_name},
    ).mappings().first()
    if row is None or not row["has_backup"]:
        raise HTTPException(status_code=409, detail="Aucune version précédente disponible pour un retour en arrière")

    for t in MODEL_LIVE_TABLES[model_name]:
        db.execute(text(f"CREATE TABLE IF NOT EXISTS analytics.{t}_candidate (LIKE analytics.{t} INCLUDING ALL)"))
        db.execute(text(f"TRUNCATE analytics.{t}_candidate"))
        db.execute(text(f"INSERT INTO analytics.{t}_candidate SELECT * FROM analytics.{t}"))
        db.execute(text(f"TRUNCATE analytics.{t}"))
        db.execute(text(f"INSERT INTO analytics.{t} SELECT * FROM analytics.{t}_previous"))

    db.execute(
        text(
            """
            UPDATE analytics.model_registry
            SET active_version = previous_version, active_metric = previous_metric,
                has_backup = FALSE, previous_version = NULL, previous_metric = NULL,
                promoted_at = NOW()
            WHERE model_name = :m
            """
        ),
        {"m": model_name},
    )
    db.commit()

    updated = db.execute(
        text(f"SELECT {_REGISTRY_COLUMNS} FROM analytics.model_registry WHERE model_name = :m"),
        {"m": model_name},
    ).mappings().first()
    return updated
