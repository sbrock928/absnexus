"""Global export template models — shared templates with per-deal node mappings."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class GlobalExportTemplate(Base):
    __tablename__ = "global_export_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
    )


class GlobalExportColumn(Base):
    __tablename__ = "global_export_column"
    __table_args__ = (
        UniqueConstraint("template_id", "position", name="uq_global_col_pos"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("global_export_template.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    header_label: Mapped[str] = mapped_column(String(100), nullable=False)
    value_type: Mapped[str] = mapped_column(String(50), nullable=False)  # distribution_node|literal|run_meta|deal_meta
    literal_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta_field: Mapped[str | None] = mapped_column(String(100), nullable=True)
    format_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    decimal_places: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prorate_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prorate_class_label: Mapped[str | None] = mapped_column(String(50), nullable=True)


class DealExportMapping(Base):
    __tablename__ = "deal_export_mapping"
    __table_args__ = (
        UniqueConstraint("deal_id", "template_id", "column_id", name="uq_deal_mapping"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("deal.id"), nullable=False)
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("global_export_template.id"), nullable=False)
    column_id: Mapped[int] = mapped_column(Integer, ForeignKey("global_export_column.id"), nullable=False)
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("dag_node.id"), nullable=False)
