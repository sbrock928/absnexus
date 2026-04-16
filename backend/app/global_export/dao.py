"""Global export data access layer."""
from sqlalchemy.orm import Session

from app.models.global_export import (
    GlobalExportTemplate,
    GlobalExportColumn,
    DealExportRow,
    DealExportCell,
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

    # ── Deal export rows + cells ──

    def list_deal_rows(self, deal_id: int, template_id: int) -> list[DealExportRow]:
        return (
            self.db.query(DealExportRow)
            .filter(
                DealExportRow.deal_id == deal_id,
                DealExportRow.template_id == template_id,
            )
            .order_by(DealExportRow.node_id, DealExportRow.row_order)
            .all()
        )

    def list_cells_for_row(self, row_id: int) -> list[DealExportCell]:
        return (
            self.db.query(DealExportCell)
            .filter(DealExportCell.row_id == row_id)
            .all()
        )

    def save_deal_config(
        self,
        deal_id: int,
        template_id: int,
        rows_data: list[dict],
    ) -> list[DealExportRow]:
        """Replace all export rows + cells for a deal+template.

        rows_data: [
            {
                "node_id": int,
                "row_order": int,
                "identifier_group": int | None,
                "cells": [
                    {"column_id": int, "value_source": str, "source_ref": str},
                    ...
                ]
            },
            ...
        ]
        """
        # Delete existing rows (cascades to cells via manual cleanup)
        existing_rows = self.list_deal_rows(deal_id, template_id)
        for row in existing_rows:
            self.db.query(DealExportCell).filter(DealExportCell.row_id == row.id).delete()
            self.db.delete(row)
        self.db.flush()

        # Insert new
        result = []
        for rd in rows_data:
            row = DealExportRow(
                deal_id=deal_id,
                template_id=template_id,
                node_id=rd["node_id"],
                row_order=rd.get("row_order", 1),
                identifier_group=rd.get("identifier_group"),
            )
            self.db.add(row)
            self.db.flush()

            for cd in rd.get("cells", []):
                cell = DealExportCell(
                    row_id=row.id,
                    column_id=cd["column_id"],
                    value_source=cd["value_source"],
                    source_ref=cd["source_ref"],
                )
                self.db.add(cell)

            self.db.flush()
            result.append(row)

        return result
