"""Deal model."""

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Deal(Base):
    __tablename__ = "deal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    servicer_id: Mapped[int] = mapped_column(Integer, ForeignKey("servicer.id"), nullable=False)
    product_type: Mapped[str] = mapped_column(String(100), nullable=False, default="ABS Auto")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    cloned_from_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("deal.id"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # ── Static deal info (populated once at deal setup) ──
    issuer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deal_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reg_ab: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    equity_cusips_involved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    initial_cutoff_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    initial_distribution_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cutoff_pool_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    # Rules for computing per-period dates each month
    distribution_day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    determination_business_days_before: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Deal-level numeric constants (auto-injected into formula context) ──
    # Fees
    servicing_fee_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    backup_servicing_fee_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    trustee_fee_monthly: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    # Overcollateralization
    target_oc_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    target_oc_floor_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    target_oc_floor_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    # Reserve account
    reserve_required_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Waterfall reconciliation config
    waterfall_starting_var: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default="total_available_funds",
    )
    waterfall_ending_var: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default="end_available_funds",
    )
    waterfall_tolerance: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
        default=Decimal("0.01"),
    )

    # Optional per-deal overrides for file output directories.
    # When null, the global settings.export_directory / settings.dag_archive_directory is used.
    export_directory_override: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dag_archive_directory_override: Mapped[str | None] = mapped_column(String(500), nullable=True)

    servicer = relationship("Servicer", lazy="joined")


class DealAccount(Base):
    """Free-form trust accounts associated with a deal (main, collection, reserve, etc.)."""

    __tablename__ = "deal_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("deal.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    account_number: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
