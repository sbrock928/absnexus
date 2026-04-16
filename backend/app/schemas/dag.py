"""DAG schemas."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class DagNodeCreate(BaseModel):
    key: str
    name: str
    node_type: str  # input_value|calculation|distribution|validation
    stream: str = "distribution"
    formula: str | None = None
    description: str | None = None
    input_source: str | None = None
    variable_id: int | None = None
    payment_type: str | None = None
    export_field: str | None = None
    tolerance: Decimal | None = None
    tolerance_type: str | None = None
    comparison_variable: str | None = None
    default_prior_value: Decimal | None = None
    position_x: int = 0
    position_y: int = 0


class DagEdgeCreate(BaseModel):
    source_key: str
    target_key: str


class DagSaveRequest(BaseModel):
    nodes: list[DagNodeCreate]
    edges: list[DagEdgeCreate]
    description: str | None = None


class DagNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key: str
    name: str
    node_type: str
    stream: str
    formula: str | None
    description: str | None
    input_source: str | None
    variable_id: int | None
    payment_type: str | None
    export_field: str | None
    tolerance: Decimal | None
    tolerance_type: str | None
    comparison_variable: str | None
    default_prior_value: Decimal | None
    position_x: int
    position_y: int
    is_active: bool


class DagEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_node_id: int
    target_node_id: int


class DagVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deal_id: int
    version_number: int
    description: str | None
    created_by: str
    created_at: datetime
    is_current: bool


class DagLoadResponse(BaseModel):
    version: DagVersionResponse
    nodes: list[DagNodeResponse]
    edges: list[DagEdgeResponse]
