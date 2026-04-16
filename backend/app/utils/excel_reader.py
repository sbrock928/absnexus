"""Excel file reader utility."""
import openpyxl
from typing import Any


class ExcelReader:
    """Read servicer Excel tapes."""

    def __init__(self, file_path: str) -> None:
        self.wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)

    def get_sheet_names(self) -> list[str]:
        return self.wb.sheetnames

    def get_cell_value(self, sheet_name: str, column_letter: str, row_number: int) -> Any:
        ws = self.wb[sheet_name]
        cell_ref = f"{column_letter}{row_number}"
        return ws[cell_ref].value

    def get_sheet_grid(self, sheet_name: str, max_rows: int = 100) -> list[list[Any]]:
        ws = self.wb[sheet_name]
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= max_rows:
                break
            rows.append(list(row))
        return rows

    def close(self) -> None:
        self.wb.close()
