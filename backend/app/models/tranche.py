"""Tranche models — deal tranches and monthly balance snapshots."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class DealTranche(Base):
    __tablename__ = "deal_tranche"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("deal.id"), nullable=False)
    class_label: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "A", "B"
    cusip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    regulation_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="combined"
    )  # combined|144a|regs
    note_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    original_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    maturity_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class TrancheBalance(Base):
    __tablename__ = "tranche_balance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tranche_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deal_tranche.id"), nullable=False
    )
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")  # manual|oracle
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
