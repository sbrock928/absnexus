"""Audit log — HTTP routing layer."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.audit.service import AuditQueryService
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.audit import AuditLogListResponse

router = APIRouter()


@router.get("/", response_model=AuditLogListResponse)
def list_audit_logs(
    entity_type: str | None = None,
    entity_id: int | None = None,
    user_id: int | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditLogListResponse:
    """List audit log entries with optional filters and pagination."""
    skip = (page - 1) * page_size
    return AuditQueryService(db).list_entries(
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=page_size,
    )


@router.get("/entity/{entity_type}/{entity_id}", response_model=AuditLogListResponse)
def audit_for_entity(
    entity_type: str,
    entity_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditLogListResponse:
    """Get audit history for a specific entity."""
    skip = (page - 1) * page_size
    return AuditQueryService(db).list_entries(
        entity_type=entity_type,
        entity_id=entity_id,
        skip=skip,
        limit=page_size,
    )
