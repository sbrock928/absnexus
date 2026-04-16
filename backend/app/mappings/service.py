"""Mapping service — extraction logic."""

from typing import Any
from sqlalchemy.orm import Session
from app.mappings.dao import MappingDAO
from app.utils.excel_reader import ExcelReader


class MappingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dao = MappingDAO(db)

    def test_extract(
        self, file_path: str, sheet_name: str, column_letter: str, row_number: int
    ) -> Any:
        reader = ExcelReader(file_path)
        try:
            return reader.get_cell_value(sheet_name, column_letter, row_number)
        finally:
            reader.close()
