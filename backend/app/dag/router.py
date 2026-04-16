"""DAG builder endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import User
from app.schemas.dag import DagSaveRequest, DagLoadResponse, DagVersionResponse
from app.dag.service import DagService

router = APIRouter()


@router.post("/{deal_id}/dag", status_code=201)
def save_dag(
    deal_id: int,
    body: DagSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    svc = DagService(db)
    version = svc.save(deal_id, body.nodes, body.edges, user.username, body.description)
    return {"version_id": version.id, "version_number": version.version_number}


@router.get("/{deal_id}/dag")
def load_dag(deal_id: int, version_id: int | None = None, db: Session = Depends(get_db)):
    svc = DagService(db)
    data = svc.load(deal_id, version_id)
    if not data:
        raise HTTPException(404, "No DAG found")
    return data


@router.get("/{deal_id}/dag/versions", response_model=list[DagVersionResponse])
def list_versions(deal_id: int, db: Session = Depends(get_db)):
    from app.dag.dao import DagDAO
    return DagDAO(db).list_versions(deal_id)


@router.post("/{deal_id}/dag/revert/{version_id}")
def revert_dag(
    deal_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    svc = DagService(db)
    version = svc.revert(deal_id, version_id, user.username)
    return {"version_id": version.id, "version_number": version.version_number}


@router.post("/{deal_id}/dag/validate")
def validate_dag(deal_id: int, db: Session = Depends(get_db)):
    errors = DagService(db).validate_dag(deal_id)
    return {"valid": len(errors) == 0, "errors": errors}


@router.patch("/{deal_id}/dag/nodes/{node_id}/deactivate", status_code=204)
def deactivate_node(
    deal_id: int, node_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    DagService(db).deactivate_node(node_id)


@router.patch("/{deal_id}/dag/nodes/{node_id}/reactivate", status_code=204)
def reactivate_node(
    deal_id: int, node_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    DagService(db).reactivate_node(node_id)
