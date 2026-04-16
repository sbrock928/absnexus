"""Variable mapping schemas."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MappingCreate(BaseModel):
    variable_id: int
    sheet_name: str
    column_letter: str
    row_number: int
    tape_label: str | None = None


class MappingUpdate(BaseModel):
    sheet_name: str | None = None
    column_letter: str | None = None
    row_number: int | None = None
    tape_label: str | None = None


class VariableBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    display_name: str | None = None


class MappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deal_id: int
    variable_id: int
    variable: VariableBrief | None = None
    sheet_name: str
    column_letter: str
    row_number: int
    tape_label: str | None
    created_at: datetime
    updated_at: datetime
