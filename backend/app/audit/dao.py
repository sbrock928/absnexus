"""Audit log data access layer."""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


class AuditLogDAO:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_filtered(
        self,
        entity_type: str | None = None,
        entity_id: int | None = None,
        user_id: int | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[tuple[AuditLog, str]], int]:
        """Return filtered audit log rows with user display names, plus total count."""
        query = self.db.query(AuditLog, User.display_name).join(User, User.id == AuditLog.user_id)

        if entity_type is not None:
            query = query.filter(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            query = query.filter(AuditLog.entity_id == entity_id)
        if user_id is not None:
            query = query.filter(AuditLog.user_id == user_id)
        if action is not None:
            query = query.filter(AuditLog.action == action)
        if date_from is not None:
            query = query.filter(AuditLog.created_at >= date_from)
        if date_to is not None:
            query = query.filter(AuditLog.created_at <= date_to)

        total = query.with_entities(func.count(AuditLog.id)).scalar() or 0

        rows = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()

        return rows, total
