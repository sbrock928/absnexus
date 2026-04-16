"""DAG builder endpoints."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, require_role, require_editable_deal
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
    _deal: Deal = Depends(require_editable_deal),
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
    _deal: Deal = Depends(require_editable_deal),
):
    svc = DagService(db)
    version = svc.revert(deal_id, version_id, user.username)
    return {"version_id": version.id, "version_number": version.version_number}


@router.post("/{deal_id}/dag/import")
def import_dag(
    deal_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
):
    """Create a new version from an uploaded JSON payload matching the dump format."""
    try:
        version = DagService(db).import_from_file(deal_id, payload, user.username)
    except Exception as exc:
        raise HTTPException(400, f"Invalid DAG payload: {exc}") from exc
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
    _deal: Deal = Depends(require_editable_deal),
):
    DagService(db).deactivate_node(node_id)


@router.patch("/{deal_id}/dag/nodes/{node_id}/reactivate", status_code=204)
def reactivate_node(
    deal_id: int, node_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
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
    _deal: Deal = Depends(require_editable_deal),
):
    node = db.query(DagNode).filter(DagNode.id == node_id, DagNode.deal_id == deal_id).first()
    if not node:
        raise HTTPException(404, "Node not found")
    changes = body.model_dump(exclude_unset=True)
    formula_changed = "formula" in changes
    for field, value in changes.items():
        setattr(node, field, value)
    db.flush()
    if formula_changed:
        DagService(db)._sync_edges_from_formula(node)
    return node


# ── Single-node / edge CRUD on the current version ──────────


class NodeCreate(BaseModel):
    # Accept either `key` or `node_key` from the frontend for compatibility.
    key: str | None = None
    node_key: str | None = None
    name: str
    node_type: str
    stream: str = "distribution"
    formula: str | None = None
    description: str | None = None
    input_source: str | None = None
    variable_id: int | None = None
    payment_type: str | None = None
    export_field: str | None = None
    tolerance: Decimal | None = None
    tolerance_type: str | None = None
    comparison_variable: str | None = None
    comparison_var: str | None = None
    default_prior_value: Decimal | None = None
    waterfall_order: int | None = None
    position_x: int = 0
    position_y: int = 0


@router.post("/{deal_id}/dag/nodes", status_code=201)
def create_node(
    deal_id: int,
    body: NodeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
):
    data = body.model_dump(exclude_unset=True)
    if "key" not in data and "node_key" in data:
        data["key"] = data.pop("node_key")
    if not data.get("key"):
        raise HTTPException(400, "node_key/key is required")
    return DagService(db).create_node(deal_id, data)


class EdgeCreate(BaseModel):
    source_node_id: int
    target_node_id: int


@router.post("/{deal_id}/dag/edges", status_code=201)
def create_edge(
    deal_id: int,
    body: EdgeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
):
    edge = DagService(db).create_edge(deal_id, body.source_node_id, body.target_node_id)
    if edge is None:
        raise HTTPException(400, "No DAG version exists for this deal")
    return {"id": edge.id, "source_node_id": edge.source_node_id, "target_node_id": edge.target_node_id}


# Bare `/dag/...` routes for the frontend calls that don't carry a deal_id.
bare_router = APIRouter()


@bare_router.patch("/dag/nodes/{node_id}")
def patch_node_bare(
    node_id: int,
    body: NodePatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    node = db.query(DagNode).filter(DagNode.id == node_id).first()
    if not node:
        raise HTTPException(404, "Node not found")
    changes = body.model_dump(exclude_unset=True)
    formula_changed = "formula" in changes
    for field, value in changes.items():
        setattr(node, field, value)
    db.flush()
    if formula_changed:
        DagService(db)._sync_edges_from_formula(node)
    return node


@bare_router.delete("/dag/nodes/{node_id}", status_code=204)
def delete_node_bare(
    node_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    if not DagService(db).delete_node(node_id):
        raise HTTPException(404, "Node not found")


@bare_router.delete("/dag/edges/{edge_id}", status_code=204)
def delete_edge_bare(
    edge_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    if not DagService(db).delete_edge(edge_id):
        raise HTTPException(404, "Edge not found")


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
    _deal: Deal = Depends(require_editable_deal),
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

