"""Deal model."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Deal(Base):
    __tablename__ = "deal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    servicer_id: Mapped[int] = mapped_column(Integer, ForeignKey("servicer.id"), nullable=False)
    product_type: Mapped[str] = mapped_column(String(100), nullable=False, default="ABS Auto")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    cloned_from_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("deal.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    servicer = relationship("Servicer", lazy="joined")
