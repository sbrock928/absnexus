"""Deal CRUD with audit logging."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import require_role
from app.models.deal import DealAccount
from app.models.processing import ProcessingRun
from app.models.user import User
from app.schemas.deal import (
    DealAccountCreate,
    DealAccountResponse,
    DealAccountUpdate,
    DealCreate,
    DealResponse,
    DealUpdate,
    PeriodPreviewResponse,
)
from app.services.deal_service import DealService
from app.services.audit_service import AuditService
from app.utils.period_dates import compute_period_dates

router = APIRouter()


@router.get("/", response_model=list[DealResponse])
def list_deals(
    status: str | None = None,
    exclude_status: str | None = None,
    db: Session = Depends(get_db),
) -> list:
    return DealService(db).list_all(status=status, exclude_status=exclude_status)


@router.get("/{deal_id}", response_model=DealResponse)
def get_deal(deal_id: int, db: Session = Depends(get_db)):
    deal = DealService(db).get(deal_id)
    if not deal:
        raise HTTPException(404, "Deal not found")
    return deal


@router.post("/", response_model=DealResponse, status_code=201)
def create_deal(
    body: DealCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    svc = DealService(db)
    deal = svc.create(body.name, body.servicer_id, body.product_type, user.username)
    AuditService(db).log_change(
        user.id, "deal", deal.id, "create", description=f"Created {deal.name}"
    )
    return deal


@router.patch("/{deal_id}", response_model=DealResponse)
def update_deal(
    deal_id: int,
    body: DealUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    deal = DealService(db).get(deal_id)
    if not deal:
        raise HTTPException(404, "Deal not found")
    changes = body.model_dump(exclude_unset=True)
    try:
        DealService(db).update(deal, **changes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    AuditService(db).log_change(user.id, "deal", deal_id, "update", changes=changes)
    return deal


@router.delete("/{deal_id}", status_code=204)
def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    deal = DealService(db).get(deal_id)
    if not deal:
        raise HTTPException(404, "Deal not found")
    AuditService(db).log_change(
        user.id, "deal", deal_id, "delete", description=f"Deleted {deal.name}"
    )
    DealService(db).delete(deal)


# ── Deal accounts (trust accounts: main, collection, reserve, etc.) ──


@router.get("/{deal_id}/accounts", response_model=list[DealAccountResponse])
def list_deal_accounts(deal_id: int, db: Session = Depends(get_db)):
    if DealService(db).get(deal_id) is None:
        raise HTTPException(404, "Deal not found")
    return (
        db.query(DealAccount)
        .filter(DealAccount.deal_id == deal_id)
        .order_by(DealAccount.position, DealAccount.id)
        .all()
    )


@router.post("/{deal_id}/accounts", response_model=DealAccountResponse, status_code=201)
def create_deal_account(
    deal_id: int,
    body: DealAccountCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    if DealService(db).get(deal_id) is None:
        raise HTTPException(404, "Deal not found")
    acct = DealAccount(deal_id=deal_id, **body.model_dump())
    db.add(acct)
    db.flush()
    return acct


@router.patch("/{deal_id}/accounts/{account_id}", response_model=DealAccountResponse)
def update_deal_account(
    deal_id: int,
    account_id: int,
    body: DealAccountUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    acct = db.query(DealAccount).filter(DealAccount.id == account_id).first()
    if acct is None or acct.deal_id != deal_id:
        raise HTTPException(404, "Account not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(acct, k, v)
    db.flush()
    return acct


@router.delete("/{deal_id}/accounts/{account_id}", status_code=204)
def delete_deal_account(
    deal_id: int,
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin", "analytics")),
):
    acct = db.query(DealAccount).filter(DealAccount.id == account_id).first()
    if acct is None or acct.deal_id != deal_id:
        raise HTTPException(404, "Account not found")
    db.delete(acct)
    db.flush()


# ── Period-date preview (read-only, no DB writes) ──


@router.get("/{deal_id}/period-preview", response_model=PeriodPreviewResponse)
def period_preview(
    deal_id: int,
    period: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
):
    deal = DealService(db).get(deal_id)
    if deal is None:
        raise HTTPException(404, "Deal not found")
    # Look up prior run's distribution date (if any) for accurate day-count.
    prior = (
        db.query(ProcessingRun)
        .filter(
            ProcessingRun.deal_id == deal_id,
            ProcessingRun.distribution_date.isnot(None),
            ProcessingRun.report_period < period,
        )
        .order_by(ProcessingRun.report_period.desc())
        .first()
    )
    prior_dist = prior.distribution_date if prior else None
    pd = compute_period_dates(deal, period, prior_dist)
    return PeriodPreviewResponse(
        report_period=period,
        distribution_date=pd.distribution_date,
        determination_date=pd.determination_date,
        days_in_period_actual=pd.days_in_period_actual,
        days_in_period_30_360=pd.days_in_period_30_360,
        anchor_date=pd.anchor_date,
        anchor_source=pd.anchor_source,
    )
