"""Tranche endpoints — nested under /api/deals/{deal_id}/tranches."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.schemas.tranche import (
    TrancheCreate, TrancheUpdate, TrancheResponse,
    BalanceSet, BalanceResponse,
)
from app.tranches.dao import TrancheDAO
from app.tranches.service import TrancheService

router = APIRouter()


@router.get("/{deal_id}/tranches", response_model=list[TrancheResponse])
def list_tranches(deal_id: int, db: Session = Depends(get_db)):
    return TrancheDAO(db).list_for_deal(deal_id)


@router.post("/{deal_id}/tranches", response_model=TrancheResponse, status_code=201)
def create_tranche(
    deal_id: int,
    body: TrancheCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    return TrancheDAO(db).create(deal_id=deal_id, **body.model_dump())


@router.patch("/{deal_id}/tranches/{tranche_id}", response_model=TrancheResponse)
def update_tranche(
    deal_id: int,
    tranche_id: int,
    body: TrancheUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    dao = TrancheDAO(db)
    t = dao.get(tranche_id)
    if not t or t.deal_id != deal_id:
        raise HTTPException(404, "Tranche not found")
    return dao.update(t, **body.model_dump(exclude_unset=True))


@router.put("/{deal_id}/tranches/{tranche_id}/balance", response_model=BalanceResponse)
def set_balance(
    deal_id: int,
    tranche_id: int,
    body: BalanceSet,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics", "analyst")),
):
    dao = TrancheDAO(db)
    t = dao.get(tranche_id)
    if not t or t.deal_id != deal_id:
        raise HTTPException(404, "Tranche not found")
    return dao.set_balance(tranche_id, body.period, body.balance, body.source)


@router.get("/{deal_id}/tranches/{tranche_id}/balances", response_model=list[BalanceResponse])
def list_balances(deal_id: int, tranche_id: int, db: Session = Depends(get_db)):
    return TrancheDAO(db).list_balances(tranche_id)


@router.get("/{deal_id}/tranche-context")
def get_tranche_context(
    deal_id: int,
    period: str,
    prior_period: str | None = None,
    db: Session = Depends(get_db),
):
    return TrancheService(db).build_tranche_context(deal_id, period, prior_period)
