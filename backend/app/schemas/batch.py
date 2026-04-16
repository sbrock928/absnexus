"""Batch run Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DealInputPayload(BaseModel):
    deal_id: int
    source_filename: str
    source_file_path: str
    source_file_hash: str


class BatchCreateRequest(BaseModel):
    report_period: str
    deal_inputs: list[DealInputPayload]


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_code: str
    report_period: str
    status: str
    deals_total: int
    deals_completed: int
    deals_failed: int
    started_by: str
    started_at: datetime | None
    completed_at: datetime | None
    execution_time_ms: int | None
    created_at: datetime
