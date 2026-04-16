"""Processing run and extracted value models."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ProcessingRun(Base):
    __tablename__ = "processing_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("deal.id"), nullable=False)
    report_period: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    # pending -> extracting -> executing -> validating -> exporting -> completed / failed
    tape_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tape_file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dag_version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("dag_version.id"), nullable=True)
    prior_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("processing_run.id"), nullable=True)
    batch_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("batch_run.id"), nullable=True,
    )
    mappings_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    tranche_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    export_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    export_file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_distribution: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    validations_passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validations_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ExtractedValue(Base):
    __tablename__ = "extracted_value"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("processing_run.id"), nullable=False)
    variable_name: Mapped[str] = mapped_column(String(100), nullable=False)
    variable_id: Mapped[int] = mapped_column(Integer, ForeignKey("variable_definition.id"), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cell_ref: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "J127"
    raw_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parsed_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False, default="decimal")
    prior_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    pct_change: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    warning: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ExecutionStep(Base):
    __tablename__ = "execution_step"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("processing_run.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("dag_node.id"), nullable=False)
    node_key: Mapped[str] = mapped_column(String(100), nullable=False)
    node_name: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    stream: Mapped[str] = mapped_column(String(50), nullable=False)
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    # Validation specific
    comparison_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    tolerance: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    tolerance_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    difference: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    passed: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1=pass, 0=fail, null=n/a
    # Export mapping
    export_field: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
