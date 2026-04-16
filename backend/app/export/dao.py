"""Export — data access layer."""

from sqlalchemy.orm import Session
from app.models.export import ExportColumn


class ExportDAO:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_columns(self, deal_id: int) -> list[ExportColumn]:
        return (
            self.db.query(ExportColumn)
            .filter(ExportColumn.deal_id == deal_id)
            .order_by(ExportColumn.position)
            .all()
        )

    def get_column(self, column_id: int) -> ExportColumn | None:
        return self.db.query(ExportColumn).filter(ExportColumn.id == column_id).first()

    def create_column(self, col: ExportColumn) -> ExportColumn:
        self.db.add(col)
        self.db.flush()
        return col

    def delete_column(self, col: ExportColumn) -> None:
        self.db.delete(col)
        self.db.flush()
