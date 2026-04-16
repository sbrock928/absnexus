"""Variable library endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.dependencies import require_role, require_editable_deal
from app.models.user import User
from app.models.variable_mapping import VariableMapping
from app.models.deal import Deal
from app.models.variable import VariableAlias
from app.schemas.variable import (
    VariableCreate, VariableUpdate, VariableResponse, AliasSet, AliasResponse,
    VariableMappingSummary, MappingDealInfo, DealMappingDetail,
)
from app.variables.dao import VariableDAO
from app.variables.service import VariableService
from app.services.deal_service import DealService

router = APIRouter()


@router.get("/", response_model=list[VariableResponse])
def list_variables(
    scope: str | None = None,
    servicer_id: int | None = None,
    deal_id: int | None = None,
    db: Session = Depends(get_db),
):
    dao = VariableDAO(db)
    if scope == "system":
        return dao.list_system()
    if scope == "servicer":
        if servicer_id:
            return dao.list_for_servicer(servicer_id)
        return dao.list_all_servicer()
    if scope == "deal":
        if deal_id:
            return dao.list_for_deal(deal_id)
        return dao.list_all_deal()
    # Default: return system
    return dao.list_system()


@router.get("/available/{deal_id}", response_model=list[VariableResponse])
def list_available(deal_id: int, db: Session = Depends(get_db)):
    deal = DealService(db).get(deal_id)
    if not deal:
        raise HTTPException(404, "Deal not found")
    return VariableService(db).list_available_for_deal(deal)


@router.post("/", response_model=VariableResponse, status_code=201)
def create_variable(
    body: VariableCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    return VariableDAO(db).create(**body.model_dump())


@router.patch("/{var_id}", response_model=VariableResponse)
def update_variable(
    var_id: int,
    body: VariableUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    dao = VariableDAO(db)
    var = dao.get(var_id)
    if not var:
        raise HTTPException(404, "Variable not found")
    return dao.update(var, **body.model_dump(exclude_unset=True))


@router.delete("/{var_id}", status_code=204)
def delete_variable(
    var_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    dao = VariableDAO(db)
    var = dao.get(var_id)
    if not var:
        raise HTTPException(404, "Variable not found")
    dao.delete(var)


@router.put("/aliases/deal/{deal_id}")
def set_deal_aliases(
    deal_id: int,
    aliases: list[AliasSet],
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
    _deal: Deal = Depends(require_editable_deal),
):
    dao = VariableDAO(db)
    for a in aliases:
        dao.set_alias(a.variable_id, a.display_alias, deal_id=deal_id)
    return {"status": "ok", "count": len(aliases)}


# ── Cross-deal mapping summary ──────────────────────────────────────────

@router.get("/mapping-summary", response_model=list[VariableMappingSummary])
def mapping_summary(db: Session = Depends(get_db)):
    """For each variable, return which deals map it."""
    rows = (
        db.query(
            VariableMapping.variable_id,
            Deal.id,
            Deal.name,
        )
        .join(Deal, Deal.id == VariableMapping.deal_id)
        .order_by(VariableMapping.variable_id, Deal.name)
        .all()
    )
    summary: dict[int, list[MappingDealInfo]] = {}
    for variable_id, deal_id, deal_name in rows:
        summary.setdefault(variable_id, []).append(
            MappingDealInfo(deal_id=deal_id, deal_name=deal_name)
        )
    return [
        VariableMappingSummary(variable_id=vid, deals=deals)
        for vid, deals in summary.items()
    ]


# ── Alias CRUD ──────────────────────────────────────────────────────────

@router.get("/{var_id}/deal-detail", response_model=list[DealMappingDetail])
def variable_deal_detail(var_id: int, db: Session = Depends(get_db)):
    """For a single variable, return every deal mapping with cell info and aliases."""
    rows = (
        db.query(
            VariableMapping.deal_id,
            Deal.name,
            Deal.status,
            VariableMapping.sheet_name,
            VariableMapping.column_letter,
            VariableMapping.row_number,
            VariableMapping.tape_label,
        )
        .join(Deal, Deal.id == VariableMapping.deal_id)
        .filter(VariableMapping.variable_id == var_id)
        .order_by(Deal.name)
        .all()
    )
    # Load aliases for this variable
    aliases = (
        db.query(VariableAlias)
        .filter(VariableAlias.variable_id == var_id)
        .all()
    )
    alias_by_deal: dict[int, str] = {}
    alias_by_servicer: dict[int, str] = {}
    for a in aliases:
        if a.deal_id:
            alias_by_deal[a.deal_id] = a.display_alias
        elif a.servicer_id:
            alias_by_servicer[a.servicer_id] = a.display_alias

    # Resolve aliases: deal > servicer
    result = []
    for deal_id, deal_name, deal_status, sheet_name, col, row, tape_label in rows:
        alias = alias_by_deal.get(deal_id)
        # Could also resolve servicer alias here if we had servicer_id on Deal
        result.append(DealMappingDetail(
            deal_id=deal_id,
            deal_name=deal_name,
            deal_status=deal_status,
            sheet_name=sheet_name,
            column_letter=col,
            row_number=row,
            tape_label=tape_label,
            alias=alias,
        ))
    return result


@router.get("/{var_id}/aliases", response_model=list[AliasResponse])
def list_aliases(var_id: int, db: Session = Depends(get_db)):
    return (
        db.query(VariableAlias)
        .filter(VariableAlias.variable_id == var_id)
        .all()
    )


@router.put("/{var_id}/aliases", response_model=AliasResponse)
def set_alias(
    var_id: int,
    body: AliasSet,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    dao = VariableDAO(db)
    var = dao.get(var_id)
    if not var:
        raise HTTPException(404, "Variable not found")
    return dao.set_alias(
        variable_id=var_id,
        display_alias=body.display_alias,
        servicer_id=body.servicer_id,
        deal_id=body.deal_id,
    )


@router.delete("/{var_id}/aliases/{alias_id}", status_code=204)
def delete_alias(
    var_id: int,
    alias_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    alias = db.query(VariableAlias).filter(
        VariableAlias.id == alias_id,
        VariableAlias.variable_id == var_id,
    ).first()
    if not alias:
        raise HTTPException(404, "Alias not found")
    db.delete(alias)
    db.flush()
