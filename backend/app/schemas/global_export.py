"""Global export template schemas."""

from pydantic import BaseModel, ConfigDict


class GlobalTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None


class GlobalColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    template_id: int
    position: int
    header_label: str
    value_type: str
    literal_value: str | None
    meta_field: str | None
    format_type: str
    decimal_places: int | None
    prorate_by: str | None
    prorate_class_label: str | None


class GlobalColumnCreate(BaseModel):
    header_label: str
    value_type: str
    literal_value: str | None = None
    meta_field: str | None = None
    format_type: str = "text"
    decimal_places: int | None = None
    prorate_by: str | None = None
    prorate_class_label: str | None = None


class GlobalColumnUpdate(BaseModel):
    header_label: str | None = None
    value_type: str | None = None
    literal_value: str | None = None
    meta_field: str | None = None
    format_type: str | None = None
    decimal_places: int | None = None
    prorate_by: str | None = None
    prorate_class_label: str | None = None


class TemplateWithColumnsResponse(BaseModel):
    template: GlobalTemplateResponse
    columns: list[GlobalColumnResponse]


class ReorderRequest(BaseModel):
    ordered_column_ids: list[int]


# ── Deal export row config ──


class DealExportCellResponse(BaseModel):
    id: int
    column_id: int
    value_source: str
    source_ref: str


class DealExportRowResponse(BaseModel):
    id: int
    node_id: int
    node_key: str | None
    node_name: str | None
    row_order: int
    identifier_group: int | None
    cells: list[DealExportCellResponse]


class DealExportConfigResponse(BaseModel):
    rows: list[DealExportRowResponse]


class DealExportCellSave(BaseModel):
    column_id: int
    value_source: str
    source_ref: str


class DealExportRowSave(BaseModel):
    node_id: int
    row_order: int = 1
    identifier_group: int | None = None
    cells: list[DealExportCellSave]


class DealExportConfigSave(BaseModel):
    rows: list[DealExportRowSave]
