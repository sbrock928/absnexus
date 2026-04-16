"""Export Pydantic schemas."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ColumnCreate(BaseModel):
    header_label: str
    value_type: str  # distribution_node | literal | run_meta | deal_meta
    node_id: int | None = None
    literal_value: str | None = None
    meta_field: str | None = None
    format_type: str = "text"
    decimal_places: int | None = 2
    prorate_by: str | None = None
    prorate_class_label: str | None = None


class ColumnUpdate(BaseModel):
    header_label: str | None = None
    value_type: str | None = None
    node_id: int | None = None
    literal_value: str | None = None
    meta_field: str | None = None
    format_type: str | None = None
    decimal_places: int | None = None
    prorate_by: str | None = None
    prorate_class_label: str | None = None


class ColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    deal_id: int
    position: int
    header_label: str
    value_type: str
    node_id: int | None
    literal_value: str | None
    meta_field: str | None
    format_type: str
    decimal_places: int | None
    prorate_by: str | None
    prorate_class_label: str | None
    created_at: datetime
    updated_at: datetime


class ReorderRequest(BaseModel):
    ordered_column_ids: list[int]


class CopyPresetRequest(BaseModel):
    preset_key: str  # system_a | system_b | system_c


class PresetInfo(BaseModel):
    key: str
    name: str
    description: str
    column_count: int


class PreviewResponse(BaseModel):
    csv: str
    row_count: int
