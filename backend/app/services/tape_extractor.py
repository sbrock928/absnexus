"""Tape extraction service — reads cells from servicer tape by mapping."""
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.processing import ProcessingRun, ExtractedValue
from app.models.variable_mapping import VariableMapping
from app.models.variable import VariableDefinition
from app.utils.excel_reader import ExcelReader


class TapeExtractor:
    def __init__(self, db: Session) -> None:
        self.db = db

    def extract_all(self, run: ProcessingRun, file_path: str) -> list[ExtractedValue]:
        """Extract all mapped variables from the tape file."""
        mappings = (
            self.db.query(VariableMapping)
            .filter(VariableMapping.deal_id == run.deal_id)
            .all()
        )

        # Snapshot mappings on the run
        snapshot = [
            {"variable_id": m.variable_id, "sheet": m.sheet_name,
             "col": m.column_letter, "row": m.row_number}
            for m in mappings
        ]
        run.mappings_snapshot = json.dumps(snapshot)

        # Find prior run for comparison
        prior_values = self._get_prior_values(run.deal_id, run.report_period)

        reader = ExcelReader(file_path)
        results: list[ExtractedValue] = []

        for m in mappings:
            var = self.db.query(VariableDefinition).filter(
                VariableDefinition.id == m.variable_id
            ).first()
            if not var:
                continue

            cell_ref = f"{m.column_letter}{m.row_number}"
            try:
                raw = reader.get_cell_value(m.sheet_name, m.column_letter, m.row_number)
            except Exception:
                raw = None

            raw_str = str(raw) if raw is not None else None
            parsed = self._parse_value(raw, var.data_type)

            # Prior month comparison
            prior_val = prior_values.get(var.name)
            pct_change = None
            warning = None
            if parsed is not None and prior_val is not None and prior_val != 0:
                pct_change = ((parsed - prior_val) / abs(prior_val) * 100).quantize(Decimal("0.01"))
                if abs(pct_change) > 50:
                    warning = f"Changed {pct_change}% from prior month ({prior_val} -> {parsed})"

            if raw is None:
                warning = f"Cell {cell_ref} on sheet '{m.sheet_name}' returned empty"

            ev = ExtractedValue(
                run_id=run.id,
                variable_name=var.name,
                variable_id=var.id,
                sheet_name=m.sheet_name,
                cell_ref=cell_ref,
                raw_value=raw_str,
                parsed_value=parsed,
                data_type=var.data_type,
                prior_value=prior_val,
                pct_change=pct_change,
                warning=warning,
            )
            self.db.add(ev)
            results.append(ev)

        reader.close()
        self.db.flush()
        return results

    def _parse_value(self, raw, data_type: str) -> Decimal | None:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return Decimal(str(raw))
        s = str(raw).strip().replace("\xa0", "").replace(",", "").replace("$", "").strip()
        if s in ("-", "", "—"):
            return Decimal("0")
        try:
            return Decimal(s)
        except (InvalidOperation, ValueError):
            return None

    def _get_prior_values(self, deal_id: int, current_period: str) -> dict[str, Decimal]:
        """Get extracted values from the prior calendar month's completed run."""
        prior_period = self._prior_calendar_month(current_period)
        prior_run = (
            self.db.query(ProcessingRun)
            .filter(
                ProcessingRun.deal_id == deal_id,
                ProcessingRun.report_period == prior_period,
                ProcessingRun.status == "completed",
            )
            .order_by(ProcessingRun.created_at.desc())
            .first()
        )
        if not prior_run:
            return {}
        prior_evs = (
            self.db.query(ExtractedValue)
            .filter(ExtractedValue.run_id == prior_run.id)
            .all()
        )
        return {ev.variable_name: ev.parsed_value for ev in prior_evs if ev.parsed_value is not None}

    def _prior_calendar_month(self, period: str) -> str:
        if not period or len(period) < 7 or "-" not in period:
            return "1970-01"
        try:
            year, month = int(period[:4]), int(period[5:7])
        except ValueError:
            return "1970-01"
        if month == 1:
            return f"{year - 1}-12"
        return f"{year}-{month - 1:02d}"
