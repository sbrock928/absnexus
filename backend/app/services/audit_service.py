"""Audit logging service."""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


def _json_default(o: Any) -> str:
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return str(o)
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log_change(
        self,
        user_id: int,
        entity_type: str,
        entity_id: int,
        action: str,
        changes: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changes=json.dumps(changes, default=_json_default) if changes else None,
            description=description,
        )
        self.db.add(entry)
        self.db.flush()
        return entry
