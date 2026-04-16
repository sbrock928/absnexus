"""Deal CRUD with audit logging."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.schemas.deal import DealCreate, DealUpdate, DealResponse
from app.services.deal_service import DealService
from app.services.audit_service import AuditService

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
