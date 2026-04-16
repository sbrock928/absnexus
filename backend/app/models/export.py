"""Export models — configurable per-deal column layouts."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# ── Legacy models (kept for migration compatibility) ──────────


class ExportTemplate(Base):
    __tablename__ = "export_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    format_type: Mapped[str] = mapped_column(String(50), nullable=False, default="row_per_payment")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ExportTemplateColumn(Base):
    __tablename__ = "export_template_column"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("export_template.id"), nullable=False
    )
    column_name: Mapped[str] = mapped_column(String(100), nullable=False)
    column_order: Mapped[int] = mapped_column(Integer, nullable=False)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False, default="string")


class ExportFieldMapping(Base):
    __tablename__ = "export_field_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("deal.id"), nullable=False)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("export_template.id"), nullable=False
    )
    node_key: Mapped[str] = mapped_column(String(100), nullable=False)
    field_code: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tranche_class: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prorate_type: Mapped[str | None] = mapped_column(String(20), nullable=True)


# ── New configurable column model ─────────────────────────────


class ExportColumn(Base):
    """A single column in a deal's export layout.

    Columns are ordered by `position`. Each column's value comes from one of:
      - distribution_node: from a DAG distribution node's calculated result
      - literal: a fixed string/number
      - run_meta: metadata from the processing run (run_code, payment_date)
      - deal_meta: metadata from the deal (deal_name, deal_id)
    """

    __tablename__ = "export_column"
    __table_args__ = (UniqueConstraint("deal_id", "position", name="uq_export_column_position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("deal.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Header in the output CSV
    header_label: Mapped[str] = mapped_column(String(100), nullable=False)

    # Value source type
    value_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # Source-specific fields (nullable — only one applies based on value_type)
    node_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("dag_node.id"),
        nullable=True,
    )
    literal_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta_field: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Format hints for output
    format_type: Mapped[str] = mapped_column(String(30), nullable=False, default="text")
    decimal_places: Mapped[int | None] = mapped_column(Integer, nullable=True, default=2)

    # Prorate split (only applies when value_type = distribution_node)
    prorate_by: Mapped[str | None] = mapped_column(String(30), nullable=True)
    prorate_class_label: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
