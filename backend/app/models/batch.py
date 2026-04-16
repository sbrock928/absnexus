"""Batch run models — parent container for multiple processing runs."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BatchRun(Base):
    """A batch run grouping multiple ProcessingRuns for a single period."""

    __tablename__ = "batch_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    report_period: Mapped[str] = mapped_column(String(7), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    # Stats populated during/after execution
    deals_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deals_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deals_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Who/when
    started_by: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Error summary (JSON array of "deal_name: error")
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
