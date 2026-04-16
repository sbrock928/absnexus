"""Deal schemas."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DealCreate(BaseModel):
    name: str
    servicer_id: int
    product_type: str = "ABS Auto"


class DealUpdate(BaseModel):
    name: str | None = None
    product_type: str | None = None
    status: Literal["draft", "active", "archived"] | None = None
    export_directory_override: str | None = None
    dag_archive_directory_override: str | None = None


class DealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    servicer_id: int
    product_type: str
    status: str
    cloned_from_id: int | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    export_directory_override: str | None = None
    dag_archive_directory_override: str | None = None
