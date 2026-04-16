"""Variable definition and alias models."""

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class VariableDefinition(Base):
    """Canonical variable with 3-tier scope: system -> servicer -> deal."""

    __tablename__ = "variable_definition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False, default="decimal")
    scope: Mapped[str] = mapped_column(String(50), nullable=False)  # system|servicer|deal
    servicer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("servicer.id"), nullable=True
    )
    deal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("deal.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class VariableAlias(Base):
    """Display alias per servicer or deal for a canonical variable."""

    __tablename__ = "variable_alias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    variable_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("variable_definition.id"), nullable=False
    )
    servicer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("servicer.id"), nullable=True
    )
    deal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("deal.id"), nullable=True)
    display_alias: Mapped[str] = mapped_column(String(255), nullable=False)
