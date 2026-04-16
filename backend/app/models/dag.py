"""DAG models — nodes, edges, and versions."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class DagVersion(Base):
    """Snapshot version of a deal's DAG. Every save creates a new row."""

    __tablename__ = "dag_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("deal.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    is_current: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)


class DagNode(Base):
    """A single node in the calculation DAG."""

    __tablename__ = "dag_node"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("deal.id"), nullable=False)
    dag_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dag_version.id"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "servicing_fee"
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # Display name
    node_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # input_value|calculation|distribution|validation
    stream: Mapped[str] = mapped_column(
        String(50), nullable=False, default="distribution"
    )  # distribution|validation
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Input node config
    input_source: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # tape|tranche|manual
    variable_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("variable_definition.id"), nullable=True
    )

    # Distribution node config
    payment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    export_field: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Validation node config
    tolerance: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    tolerance_type: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # absolute|percentage
    comparison_variable: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Prior month default (first month only)
    default_prior_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    # Waterfall ordering for distribution nodes
    waterfall_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Visual position
    position_x: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position_y: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)


class DagEdge(Base):
    """Directed edge between two DAG nodes."""

    __tablename__ = "dag_edge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dag_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dag_version.id"), nullable=False
    )
    source_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("dag_node.id"), nullable=False)
    target_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("dag_node.id"), nullable=False)
