"""DAG builder endpoints."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import User
from app.models.dag import DagNode
from app.models.deal import Deal
from app.schemas.dag import DagSaveRequest, DagLoadResponse, DagVersionResponse
from app.dag.service import DagService
from app.services.deal_service import DealService

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


# ── Node patch (update individual fields) ────────────────────


class NodePatch(BaseModel):
    name: str | None = None
    formula: str | None = None
    payment_type: str | None = None
    export_field: str | None = None
    waterfall_order: int | None = None
    tolerance: Decimal | None = None
    tolerance_type: str | None = None
    comparison_variable: str | None = None
    position_x: int | None = None
    position_y: int | None = None


@router.patch("/{deal_id}/dag/nodes/{node_id}")
def patch_node(
    deal_id: int,
    node_id: int,
    body: NodePatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    node = db.query(DagNode).filter(DagNode.id == node_id, DagNode.deal_id == deal_id).first()
    if not node:
        raise HTTPException(404, "Node not found")
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(node, field, value)
    db.flush()
    return node


# ── Waterfall config on deal ─────────────────────────────────


class WaterfallConfigUpdate(BaseModel):
    waterfall_starting_var: str | None = None
    waterfall_ending_var: str | None = None
    waterfall_tolerance: Decimal | None = None


@router.patch("/{deal_id}/waterfall-config")
def update_waterfall_config(
    deal_id: int,
    payload: WaterfallConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "analytics")),
):
    deal = DealService(db).get(deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found.")
    if payload.waterfall_starting_var is not None:
        deal.waterfall_starting_var = payload.waterfall_starting_var
    if payload.waterfall_ending_var is not None:
        deal.waterfall_ending_var = payload.waterfall_ending_var
    if payload.waterfall_tolerance is not None:
        deal.waterfall_tolerance = payload.waterfall_tolerance
    db.flush()
    return {
        "starting_var": deal.waterfall_starting_var,
        "ending_var": deal.waterfall_ending_var,
        "tolerance": str(deal.waterfall_tolerance),
    }

