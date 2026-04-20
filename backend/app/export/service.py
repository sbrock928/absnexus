"""Export — CSV generation from configurable columns."""

import csv
import hashlib
import io
import os
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core import settings
from app.export.dao import ExportDAO
from app.models.deal import Deal
from app.models.export import ExportColumn
from app.models.processing import ProcessingRun, ExecutionStep
from app.tranches.dao import TrancheDAO

# Preset layouts for "Copy from preset" feature
PRESETS: dict[str, dict[str, object]] = {
    "system_a": {
        "name": "System A — Row per payment",
        "description": "One row per distribution node",
        "columns": [
            {
                "header_label": "DEAL_ID",
                "value_type": "deal_meta",
                "meta_field": "deal_id",
                "format_type": "text",
            },
            {
                "header_label": "PAYMENT_DATE",
                "value_type": "run_meta",
                "meta_field": "payment_date",
                "format_type": "text",
            },
            {
                "header_label": "PAYMENT_TYPE",
                "value_type": "literal",
                "literal_value": "INTEREST",
                "format_type": "text",
            },
            {
                "header_label": "CLASS",
                "value_type": "literal",
                "literal_value": "A",
                "format_type": "text",
            },
            {
                "header_label": "FIELD_CODE",
                "value_type": "literal",
                "literal_value": "INT_PMT_A",
                "format_type": "text",
            },
            {
                "header_label": "AMOUNT",
                "value_type": "distribution_node",
                "format_type": "decimal",
                "decimal_places": 2,
            },
            {
                "header_label": "RUN_ID",
                "value_type": "run_meta",
                "meta_field": "run_code",
                "format_type": "text",
            },
        ],
    },
    "system_b": {
        "name": "System B — Wide with 144A/RegS",
        "description": "Prorate split columns per field",
        "columns": [
            {
                "header_label": "DEAL_ID",
                "value_type": "deal_meta",
                "meta_field": "deal_id",
                "format_type": "text",
            },
            {
                "header_label": "PAYMENT_DATE",
                "value_type": "run_meta",
                "meta_field": "payment_date",
                "format_type": "text",
            },
            {
                "header_label": "FIELD_CODE",
                "value_type": "literal",
                "literal_value": "INT_PMT_A",
                "format_type": "text",
            },
            {
                "header_label": "AMOUNT_144A",
                "value_type": "distribution_node",
                "prorate_by": "144a",
                "format_type": "decimal",
                "decimal_places": 2,
            },
            {
                "header_label": "AMOUNT_REGS",
                "value_type": "distribution_node",
                "prorate_by": "regs",
                "format_type": "decimal",
                "decimal_places": 2,
            },
            {
                "header_label": "AMOUNT_TOTAL",
                "value_type": "distribution_node",
                "format_type": "decimal",
                "decimal_places": 2,
            },
            {
                "header_label": "RUN_ID",
                "value_type": "run_meta",
                "meta_field": "run_code",
                "format_type": "text",
            },
        ],
    },
    "system_c": {
        "name": "System C — CUSIP level",
        "description": "One row per CUSIP",
        "columns": [
            {
                "header_label": "DEAL_ID",
                "value_type": "deal_meta",
                "meta_field": "deal_id",
                "format_type": "text",
            },
            {
                "header_label": "PAYMENT_DATE",
                "value_type": "run_meta",
                "meta_field": "payment_date",
                "format_type": "text",
            },
            {
                "header_label": "CUSIP",
                "value_type": "literal",
                "literal_value": "",
                "format_type": "text",
            },
            {
                "header_label": "PAYMENT_TYPE",
                "value_type": "literal",
                "literal_value": "INTEREST",
                "format_type": "text",
            },
            {
                "header_label": "AMOUNT",
                "value_type": "distribution_node",
                "format_type": "decimal",
                "decimal_places": 2,
            },
            {
                "header_label": "RUN_ID",
                "value_type": "run_meta",
                "meta_field": "run_code",
                "format_type": "text",
            },
        ],
    },
}


class ExportColumnService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dao = ExportDAO(db)
        self.tranche_dao = TrancheDAO(db)

    # ── Columns CRUD ──────────────────────────────────────────

    def list_columns(self, deal_id: int) -> list[ExportColumn]:
        return self.dao.list_columns(deal_id)

    def get_column(self, column_id: int) -> ExportColumn | None:
        return self.dao.get_column(column_id)

    def create_column(
        self,
        deal_id: int,
        header_label: str,
        value_type: str,
        node_id: int | None = None,
        literal_value: str | None = None,
        meta_field: str | None = None,
        format_type: str = "text",
        decimal_places: int | None = 2,
        prorate_by: str | None = None,
        prorate_class_label: str | None = None,
        position: int | None = None,
    ) -> ExportColumn:
        # Auto-assign position at end if not specified
        if position is None:
            existing = self.dao.list_columns(deal_id)
            position = len(existing) + 1

        col = ExportColumn(
            deal_id=deal_id,
            position=position,
            header_label=header_label,
            value_type=value_type,
            node_id=node_id,
            literal_value=literal_value,
            meta_field=meta_field,
            format_type=format_type,
            decimal_places=decimal_places,
            prorate_by=prorate_by,
            prorate_class_label=prorate_class_label,
        )
        return self.dao.create_column(col)

    def update_column(self, col: ExportColumn, **fields) -> ExportColumn:
        allowed = {
            "header_label",
            "value_type",
            "node_id",
            "literal_value",
            "meta_field",
            "format_type",
            "decimal_places",
            "prorate_by",
            "prorate_class_label",
        }
        for f, v in fields.items():
            if f in allowed:
                setattr(col, f, v)
        self.db.flush()
        return col

    def delete_column(self, col: ExportColumn) -> None:
        self.dao.delete_column(col)

    def reorder_columns(self, deal_id: int, ordered_ids: list[int]) -> list[ExportColumn]:
        """Reorder columns by setting position according to list order."""
        cols = {c.id: c for c in self.dao.list_columns(deal_id)}
        # Two-pass to avoid unique constraint conflicts:
        # 1) Set all positions to negative temporaries
        for idx, col_id in enumerate(ordered_ids):
            if col_id in cols:
                cols[col_id].position = -(idx + 1)
        self.db.flush()
        # 2) Set final positive positions
        for idx, col_id in enumerate(ordered_ids, start=1):
            if col_id in cols:
                cols[col_id].position = idx
        self.db.flush()
        return self.dao.list_columns(deal_id)

    def copy_preset(self, deal_id: int, preset_key: str) -> list[ExportColumn]:
        """Replace all columns with a preset's columns."""
        if preset_key not in PRESETS:
            raise ValueError(f"Unknown preset: {preset_key}")

        # Clear existing
        for col in self.dao.list_columns(deal_id):
            self.dao.delete_column(col)

        # Create preset columns
        columns_def = PRESETS[preset_key]["columns"]
        assert isinstance(columns_def, list)
        for i, col_def in enumerate(columns_def, start=1):
            col = ExportColumn(deal_id=deal_id, position=i, **col_def)
            self.dao.create_column(col)

        return self.dao.list_columns(deal_id)

    # ── Preview ───────────────────────────────────────────────

    def preview(self, deal_id: int, run_id: int | None = None) -> str:
        """Generate a preview CSV. If run_id given and run completed, uses real values."""
        cols = self.dao.list_columns(deal_id)
        if not cols:
            return "No columns configured."

        if run_id:
            run = self.db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
            if run and run.status == "completed":
                return self._generate(run, cols)

        # Generate sample output with placeholders
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([c.header_label for c in cols])

        # 2 sample rows
        for _ in range(2):
            row: list[str] = []
            for c in cols:
                if c.value_type == "distribution_node":
                    row.append("123456.78" if c.format_type == "decimal" else "sample")
                elif c.value_type == "literal":
                    row.append(c.literal_value or "")
                elif c.value_type == "run_meta":
                    row.append(f"<{c.meta_field}>")
                elif c.value_type == "deal_meta":
                    row.append(f"<{c.meta_field}>")
                else:
                    row.append("")
            writer.writerow(row)

        return out.getvalue()

    # ── Generate ──────────────────────────────────────────────

    def generate_csv(self, run: ProcessingRun) -> tuple[str, str]:
        """Generate the actual export CSV for a completed run. Returns (path, hash)."""
        if run.status != "completed":
            raise ValueError(f"Cannot export: run status is '{run.status}'.")

        cols = self.dao.list_columns(run.deal_id)
        if not cols:
            raise ValueError("No export columns configured for this deal.")

        content = self._generate(run, cols)

        # Save file
        deal = self.db.query(Deal).filter(Deal.id == run.deal_id).first()
        deal_name = deal.name.replace(" ", "_") if deal else f"deal_{run.deal_id}"
        period = run.report_period or "unknown"
        filename = f"{deal_name}_EXPORT_{period.replace('-', '')}.csv"
        dest_dir = os.path.join(settings.export_directory, str(run.deal_id), period)
        os.makedirs(dest_dir, exist_ok=True)
        file_path = os.path.join(dest_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        file_hash = hashlib.sha256(content.encode()).hexdigest()
        run.export_file_path = file_path
        run.export_file_hash = file_hash
        self.db.flush()

        return file_path, file_hash

    def _generate(self, run: ProcessingRun, cols: list[ExportColumn]) -> str:
        """Core CSV generation logic."""
        deal = self.db.query(Deal).filter(Deal.id == run.deal_id).first()

        # Load distribution execution steps
        dist_steps = (
            self.db.query(ExecutionStep)
            .filter(
                ExecutionStep.run_id == run.id,
                ExecutionStep.node_type == "distribution",
            )
            .order_by(ExecutionStep.step_order)
            .all()
        )
        step_by_node: dict[int, ExecutionStep] = {s.node_id: s for s in dist_steps}

        # Determine row drivers: distribution_node columns with node_id
        node_cols = [c for c in cols if c.value_type == "distribution_node" and c.node_id]
        distinct_node_ids = list({c.node_id for c in node_cols if c.node_id in step_by_node})

        if not distinct_node_ids:
            # Fall back to all distribution steps, or a single row
            distinct_node_ids = [s.node_id for s in dist_steps] if dist_steps else [None]  # type: ignore

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([c.header_label for c in cols])

        for node_id in distinct_node_ids:
            step = step_by_node.get(node_id) if node_id else None
            row = [self._resolve_column(c, run, deal, step) for c in cols]
            writer.writerow(row)

        return out.getvalue()

    def _resolve_column(
        self,
        col: ExportColumn,
        run: ProcessingRun,
        deal: Deal | None,
        step: ExecutionStep | None,
    ) -> str:
        """Resolve a single cell value for a row."""
        if col.value_type == "distribution_node":
            if step is None or step.result is None:
                return ""
            value = step.result
            if col.prorate_by:
                value = self._apply_prorate(value, col, run)
            return self._format_value(value, col)

        elif col.value_type == "literal":
            return col.literal_value or ""

        elif col.value_type == "run_meta":
            if col.meta_field == "run_code":
                return f"RUN-{run.id}"
            elif col.meta_field == "payment_date":
                return run.report_period or ""
            elif col.meta_field == "report_period":
                return run.report_period or ""
            elif col.meta_field == "distribution_date":
                return run.distribution_date.isoformat() if run.distribution_date else ""
            elif col.meta_field == "determination_date":
                return run.determination_date.isoformat() if run.determination_date else ""
            elif col.meta_field == "days_in_period_actual":
                return str(run.days_in_period_actual) if run.days_in_period_actual is not None else ""
            elif col.meta_field == "days_in_period_30_360":
                return str(run.days_in_period_30_360) if run.days_in_period_30_360 is not None else ""
            return ""

        elif col.value_type == "deal_meta":
            if not deal:
                return ""
            if col.meta_field == "deal_id":
                return deal.name.replace(" ", "_") if deal.name else f"deal_{deal.id}"
            elif col.meta_field == "deal_name":
                return deal.name
            elif col.meta_field == "product_type":
                return deal.product_type or ""
            elif col.meta_field == "issuer_name":
                return deal.issuer_name or ""
            elif col.meta_field == "deal_key":
                return deal.deal_key or ""
            elif col.meta_field == "closing_date":
                return deal.closing_date.isoformat() if deal.closing_date else ""
            elif col.meta_field == "initial_cutoff_date":
                return deal.initial_cutoff_date.isoformat() if deal.initial_cutoff_date else ""
            elif col.meta_field == "initial_distribution_date":
                return (
                    deal.initial_distribution_date.isoformat()
                    if deal.initial_distribution_date
                    else ""
                )
            elif col.meta_field == "cutoff_pool_balance":
                return str(deal.cutoff_pool_balance) if deal.cutoff_pool_balance is not None else ""
            return ""

        elif col.value_type == "deal_account":
            # meta_field stores the account label (case-insensitive match).
            if not deal or not col.meta_field:
                return ""
            from app.models.deal import DealAccount

            acct = (
                self.db.query(DealAccount)
                .filter(
                    DealAccount.deal_id == deal.id,
                    DealAccount.label.ilike(col.meta_field),
                )
                .first()
            )
            return acct.account_number if acct else ""

        return ""

    def _apply_prorate(
        self,
        value: Decimal,
        col: ExportColumn,
        run: ProcessingRun,
    ) -> Decimal:
        """Apply 144A/RegS prorate ratio to a value."""
        class_label = col.prorate_class_label
        if not class_label:
            return value

        tranches = self.tranche_dao.list_for_deal(run.deal_id)
        class_tranches = [t for t in tranches if t.class_label.lower() == class_label.lower()]

        bal_144a = Decimal("0")
        bal_regs = Decimal("0")
        for t in class_tranches:
            bal = self.tranche_dao.get_balance(t.id, run.report_period or "")
            amount = bal.balance if bal else (t.original_balance or Decimal("0"))
            if t.regulation_type == "144a":
                bal_144a = amount
            elif t.regulation_type == "regs":
                bal_regs = amount

        total = bal_144a + bal_regs
        if total == Decimal("0"):
            return value

        if col.prorate_by == "144a":
            return value * (bal_144a / total)
        elif col.prorate_by == "regs":
            return value * (bal_regs / total)
        return value

    @staticmethod
    def _format_value(value, col: ExportColumn) -> str:
        if col.format_type == "decimal" and isinstance(value, Decimal):
            places = col.decimal_places or 2
            return f"{value:.{places}f}"
        if col.format_type == "integer" and isinstance(value, Decimal):
            return f"{int(value)}"
        return str(value) if value is not None else ""
