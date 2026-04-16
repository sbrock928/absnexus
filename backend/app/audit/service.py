"""Audit log query service (read-only)."""
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.audit.dao import AuditLogDAO
from app.schemas.audit import AuditLogListResponse, AuditLogResponse


class AuditQueryService:
    """Read-only service for querying audit log entries.

    Distinct from ``app.services.audit_service.AuditService`` which handles writes.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.dao = AuditLogDAO(db)

    def list_entries(
        self,
        entity_type: str | None = None,
        entity_id: int | None = None,
        user_id: int | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> AuditLogListResponse:
        rows, total = self.dao.list_filtered(
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )

        items = [self._to_response(log, display_name) for log, display_name in rows]
        page = skip // limit + 1 if limit > 0 else 1

        return AuditLogListResponse(
            items=items,
            total=total,
            page=page,
            page_size=limit,
            has_more=(skip + limit < total),
        )

    @staticmethod
    def _to_response(log, display_name: str) -> AuditLogResponse:  # type: ignore[type-arg]
        changes = None
        if log.changes:
            try:
                changes = json.loads(log.changes)
            except (json.JSONDecodeError, TypeError):
                changes = None

        return AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            user_display_name=display_name,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            action=log.action,
            changes=changes,
            description=log.description,
            created_at=log.created_at,
        )
