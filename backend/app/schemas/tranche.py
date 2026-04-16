"""Tranche schemas."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class TrancheCreate(BaseModel):
    class_label: str
    cusip: str | None = None
    regulation_type: str = "combined"
    note_rate: Decimal | None = None
    original_balance: Decimal | None = None
    maturity_date: str | None = None


class TrancheUpdate(BaseModel):
    class_label: str | None = None
    cusip: str | None = None
    note_rate: Decimal | None = None
    original_balance: Decimal | None = None
    maturity_date: str | None = None


class TrancheResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deal_id: int
    class_label: str
    cusip: str | None
    regulation_type: str
    note_rate: Decimal | None
    original_balance: Decimal | None
    maturity_date: str | None
    is_active: bool
    created_at: datetime


class BalanceSet(BaseModel):
    period: str
    balance: Decimal
    source: str = "manual"


class BalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tranche_id: int
    period: str
    balance: Decimal
    source: str
    updated_at: datetime
