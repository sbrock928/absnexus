"""Variable mapping — maps a variable to a specific cell in a servicer tape."""

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class VariableMapping(Base):
    __tablename__ = "variable_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("deal.id"), nullable=False)
    variable_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("variable_definition.id"), nullable=False
    )
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    column_letter: Mapped[str] = mapped_column(String(10), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    tape_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    variable = relationship("VariableDefinition", lazy="joined")
