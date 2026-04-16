"""Variable schemas."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class VariableCreate(BaseModel):
    name: str
    display_name: str | None = None
    data_type: str = "decimal"
    scope: str = "system"
    servicer_id: int | None = None
    deal_id: int | None = None
    description: str | None = None


class VariableUpdate(BaseModel):
    display_name: str | None = None
    data_type: str | None = None
    description: str | None = None


class VariableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    display_name: str | None
    data_type: str
    scope: str
    servicer_id: int | None
    deal_id: int | None
    description: str | None
    created_at: datetime


class AliasSet(BaseModel):
    variable_id: int | None = None
    display_alias: str
    servicer_id: int | None = None
    deal_id: int | None = None


class AliasResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    variable_id: int
    servicer_id: int | None
    deal_id: int | None
    display_alias: str


class MappingDealInfo(BaseModel):
    deal_id: int
    deal_name: str


class VariableMappingSummary(BaseModel):
    variable_id: int
    deals: list[MappingDealInfo]


class DealMappingDetail(BaseModel):
    deal_id: int
    deal_name: str
    deal_status: str
    sheet_name: str
    column_letter: str
    row_number: int
    tape_label: str | None
    alias: str | None = None
