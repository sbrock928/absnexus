"""Audit log schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    user_display_name: str
    entity_type: str
    entity_id: int
    action: str
    changes: dict[str, Any] | None
    description: str | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
