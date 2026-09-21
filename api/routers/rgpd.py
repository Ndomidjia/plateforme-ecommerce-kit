"""Endpoints RGPD (droit d'accès/portabilité + droit à l'oubli) sur churn.

Réservés aux admins : contrairement aux endpoints /analytics (données déjà
agrégées), ceux-ci manipulent des données personnelles brutes.

Chaque action est tracée dans app.rgpd_audit_log (qui, quoi, quand) :
principe de responsabilité (accountability) du RGPD.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection

from database import get_db
from deps import require_role

router = APIRouter(prefix="/rgpd", tags=["rgpd"])

def _log_action(db: Connection, action: str, schema_name: str, subject_id: str, requested_by: str):
    db.execute(
        text("INSERT INTO app.rgpd_audit_log (action, schema_name, subject_id, requested_by) "
             "VALUES (:action, :schema_name, :subject_id, :requested_by)"),
        {"action": action, "schema_name": schema_name, "subject_id": subject_id, "requested_by": requested_by},
    )

@router.get("/churn/{customer_id}/export")
def export_churn_customer(
    customer_id: int,
    db: Connection = Depends(get_db),
    admin: dict = Depends(require_role("admin")),
):
    """Droit d'accès / portabilité : renvoie l'intégralité des données du client."""
    row = db.execute(
        text("SELECT * FROM churn.customer_profiles WHERE customer_id = :cid"),
        {"cid": customer_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Client inconnu")

    _log_action(db, "export", "churn", str(customer_id), admin["username"])
    db.commit()
    return dict(row)

@router.delete("/churn/{customer_id}")
def erase_churn_customer(
    customer_id: int,
    db: Connection = Depends(get_db),
    admin: dict = Depends(require_role("admin")),
):
    """Droit à l'oubli : anonymise les champs identifiants (âge, genre, pays,
    ville). Les métriques comportementales/agrégées sont conservées (elles ne
    permettent pas, seules, de réidentifier le client) pour ne pas invalider
    les statistiques et modèles déjà calculés.
    """
    result = db.execute(
        text("UPDATE churn.customer_profiles "
             "SET age = NULL, gender = NULL, country = NULL, city = NULL "
             "WHERE customer_id = :cid"),
        {"cid": customer_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Client inconnu")

    _log_action(db, "erasure", "churn", str(customer_id), admin["username"])
    db.commit()
    return {"detail": f"Client {customer_id} anonymisé"}
