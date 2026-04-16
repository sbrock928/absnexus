"""Global export data access layer."""
from sqlalchemy.orm import Session

from app.models.global_export import (
    GlobalExportTemplate,
    GlobalExportColumn,
    DealExportMapping,
)


class GlobalExportDAO:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Templates ──

    def list_templates(self) -> list[GlobalExportTemplate]:
        return self.db.query(GlobalExportTemplate).order_by(GlobalExportTemplate.id).all()

    def get_template(self, template_id: int) -> GlobalExportTemplate | None:
        return self.db.query(GlobalExportTemplate).filter(
            GlobalExportTemplate.id == template_id,
        ).first()

    # ── Columns ──

    def list_columns(self, template_id: int) -> list[GlobalExportColumn]:
        return (
            self.db.query(GlobalExportColumn)
            .filter(GlobalExportColumn.template_id == template_id)
            .order_by(GlobalExportColumn.position)
            .all()
        )

    def get_column(self, column_id: int) -> GlobalExportColumn | None:
        return self.db.query(GlobalExportColumn).filter(
            GlobalExportColumn.id == column_id,
        ).first()

    def create_column(self, template_id: int, position: int, **kwargs: object) -> GlobalExportColumn:
        col = GlobalExportColumn(template_id=template_id, position=position, **kwargs)
        self.db.add(col)
        self.db.flush()
        return col

    def update_column(self, col: GlobalExportColumn, **kwargs: object) -> GlobalExportColumn:
        for key, value in kwargs.items():
            setattr(col, key, value)
        self.db.flush()
        return col

    def delete_column(self, col: GlobalExportColumn) -> None:
        self.db.delete(col)
        self.db.flush()

    def next_position(self, template_id: int) -> int:
        from sqlalchemy import func
        result = self.db.query(func.max(GlobalExportColumn.position)).filter(
            GlobalExportColumn.template_id == template_id,
        ).scalar()
        return (result or 0) + 1

    def reorder_columns(self, template_id: int, ordered_ids: list[int]) -> list[GlobalExportColumn]:
        columns = self.list_columns(template_id)
        col_map = {c.id: c for c in columns}
        for pos, col_id in enumerate(ordered_ids, start=1):
            col = col_map.get(col_id)
            if col:
                col.position = pos
        self.db.flush()
        return self.list_columns(template_id)

    # ── Deal mappings ──

    def list_deal_mappings(self, deal_id: int, template_id: int) -> list[DealExportMapping]:
        return (
            self.db.query(DealExportMapping)
            .filter(
                DealExportMapping.deal_id == deal_id,
                DealExportMapping.template_id == template_id,
            )
            .all()
        )

    def save_deal_mappings(
        self,
        deal_id: int,
        template_id: int,
        mappings: list[dict[str, int]],
    ) -> list[DealExportMapping]:
        """Replace all mappings for a deal+template with the provided list."""
        # Delete existing
        self.db.query(DealExportMapping).filter(
            DealExportMapping.deal_id == deal_id,
            DealExportMapping.template_id == template_id,
        ).delete()
        self.db.flush()

        # Insert new
        result = []
        for m in mappings:
            mapping = DealExportMapping(
                deal_id=deal_id,
                template_id=template_id,
                column_id=m["column_id"],
                node_id=m["node_id"],
            )
            self.db.add(mapping)
            self.db.flush()
            result.append(mapping)
        return result
