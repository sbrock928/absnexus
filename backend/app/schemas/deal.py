"""Deal schemas."""

from datetime import date, datetime
from decimal import Decimal
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

    # Static deal info
    issuer_name: str | None = None
    deal_key: str | None = None
    reg_ab: bool | None = None
    equity_cusips_involved: bool | None = None
    closing_date: date | None = None
    initial_cutoff_date: date | None = None
    initial_distribution_date: date | None = None
    cutoff_pool_balance: Decimal | None = None
    distribution_day_of_month: int | None = None
    determination_business_days_before: int | None = None

    # Deal-level numeric constants
    servicing_fee_pct: Decimal | None = None
    backup_servicing_fee_pct: Decimal | None = None
    trustee_fee_monthly: Decimal | None = None
    target_oc_pct: Decimal | None = None
    target_oc_floor_pct: Decimal | None = None
    target_oc_floor_amount: Decimal | None = None
    reserve_required_pct: Decimal | None = None


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

    # Static deal info
    issuer_name: str | None = None
    deal_key: str | None = None
    reg_ab: bool = False
    equity_cusips_involved: bool = False
    closing_date: date | None = None
    initial_cutoff_date: date | None = None
    initial_distribution_date: date | None = None
    cutoff_pool_balance: Decimal | None = None
    distribution_day_of_month: int | None = None
    determination_business_days_before: int | None = None

    # Deal-level numeric constants
    servicing_fee_pct: Decimal | None = None
    backup_servicing_fee_pct: Decimal | None = None
    trustee_fee_monthly: Decimal | None = None
    target_oc_pct: Decimal | None = None
    target_oc_floor_pct: Decimal | None = None
    target_oc_floor_amount: Decimal | None = None
    reserve_required_pct: Decimal | None = None


# ── Deal accounts ──


class DealAccountCreate(BaseModel):
    label: str
    account_number: str
    position: int = 0


class DealAccountUpdate(BaseModel):
    label: str | None = None
    account_number: str | None = None
    position: int | None = None


class DealAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    deal_id: int
    label: str
    account_number: str
    position: int
    created_at: datetime


# ── Period preview ──


class PeriodPreviewResponse(BaseModel):
    report_period: str
    distribution_date: date | None = None
    determination_date: date | None = None
    days_in_period_actual: int | None = None
    days_in_period_30_360: int | None = None
    anchor_date: date | None = None
    anchor_source: str | None = None  # "prior_run" | "prior_month_computed" | "initial_cutoff"
