"""Global export service — templates, mappings, CSV generation."""
import csv
import hashlib
import io
import os
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core import settings
from app.global_export.dao import GlobalExportDAO
from app.models.dag import DagNode
from app.models.deal import Deal
from app.models.global_export import GlobalExportColumn, DealExportMapping
from app.models.processing import ProcessingRun, ExecutionStep
from app.schemas.global_export import (
    DealMappingResponse,
    GlobalTemplateResponse,
    TemplateWithColumnsResponse,
    GlobalColumnResponse,
)
from app.tranches.dao import TrancheDAO


class GlobalExportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dao = GlobalExportDAO(db)
        self.tranche_dao = TrancheDAO(db)

    # ── Templates ──

    def list_templates(self) -> list[GlobalTemplateResponse]:
        templates = self.dao.list_templates()
        cols_counts: dict[int, int] = {}
        for t in templates:
            cols_counts[t.id] = len(self.dao.list_columns(t.id))
        return [
            GlobalTemplateResponse(
                id=t.id, name=t.name, description=t.description,
            )
            for t in templates
        ]

    def get_template_with_columns(self, template_id: int) -> TemplateWithColumnsResponse:
        t = self.dao.get_template(template_id)
        if t is None:
            raise ValueError("Template not found.")
        cols = self.dao.list_columns(template_id)
        return TemplateWithColumnsResponse(
            template=GlobalTemplateResponse(id=t.id, name=t.name, description=t.description),
            columns=[GlobalColumnResponse.model_validate(c) for c in cols],
        )

    # ── Deal mappings ──

    def get_deal_mappings(self, deal_id: int, template_id: int) -> list[DealMappingResponse]:
        mappings = self.dao.list_deal_mappings(deal_id, template_id)
        result = []
        for m in mappings:
            col = self.dao.get_column(m.column_id)
            node = self.db.query(DagNode).filter(DagNode.id == m.node_id).first()
            result.append(DealMappingResponse(
                id=m.id,
                column_id=m.column_id,
                node_id=m.node_id,
                header_label=col.header_label if col else None,
                node_key=node.key if node else None,
                node_name=node.name if node else None,
            ))
        return result

    def save_deal_mappings(
        self,
        deal_id: int,
        template_id: int,
        mappings: list[dict[str, int]],
    ) -> list[DealExportMapping]:
        return self.dao.save_deal_mappings(deal_id, template_id, mappings)

    # ── CSV generation ──

    def generate_csv(self, run: ProcessingRun, template_id: int) -> tuple[str, str]:
        """Generate CSV for a run using a global template + deal mappings."""
        if run.status != "completed":
            raise ValueError(f"Cannot export: run status is '{run.status}'.")

        cols = self.dao.list_columns(template_id)
        if not cols:
            raise ValueError("No columns configured for this template.")

        # Build mapping: column_id → node_id for this deal
        deal_mappings = self.dao.list_deal_mappings(run.deal_id, template_id)
        col_to_node: dict[int, int] = {m.column_id: m.node_id for m in deal_mappings}

        content = self._generate(run, cols, col_to_node)

        # Save file
        deal = self.db.query(Deal).filter(Deal.id == run.deal_id).first()
        template = self.dao.get_template(template_id)
        deal_name = deal.name.replace(" ", "_") if deal else f"deal_{run.deal_id}"
        tmpl_name = template.name.replace(" ", "_") if template else f"tmpl_{template_id}"
        period = run.report_period or "unknown"
        filename = f"{deal_name}_{tmpl_name}_{period.replace('-', '')}.csv"
        dest_dir = os.path.join(settings.export_directory, str(run.deal_id), period)
        os.makedirs(dest_dir, exist_ok=True)
        file_path = os.path.join(dest_dir, filename)

        with open(file_path, "w") as f:
            f.write(content)

        file_hash = hashlib.sha256(content.encode()).hexdigest()
        run.export_file_path = file_path
        run.export_file_hash = file_hash
        self.db.flush()

        return file_path, file_hash

    def preview(self, deal_id: int, template_id: int, run_id: int | None = None) -> str:
        """Generate preview CSV text without saving to disk."""
        cols = self.dao.list_columns(template_id)
        if not cols:
            return ""

        deal_mappings = self.dao.list_deal_mappings(deal_id, template_id)
        col_to_node: dict[int, int] = {m.column_id: m.node_id for m in deal_mappings}

        if run_id:
            run = self.db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
            if run:
                return self._generate(run, cols, col_to_node)

        # No run — produce sample row with placeholders
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([c.header_label for c in cols])
        writer.writerow([self._placeholder(c) for c in cols])
        return out.getvalue()

    def _generate(
        self,
        run: ProcessingRun,
        cols: list[GlobalExportColumn],
        col_to_node: dict[int, int],
    ) -> str:
        deal = self.db.query(Deal).filter(Deal.id == run.deal_id).first()

        dist_steps = (
            self.db.query(ExecutionStep)
            .filter(ExecutionStep.run_id == run.id, ExecutionStep.node_type == "distribution")
            .order_by(ExecutionStep.step_order)
            .all()
        )
        step_by_node: dict[int, ExecutionStep] = {s.node_id: s for s in dist_steps}

        # Determine row drivers: distinct node_ids from mappings that have execution results
        mapped_node_ids = list({nid for nid in col_to_node.values() if nid in step_by_node})
        if not mapped_node_ids:
            mapped_node_ids = [s.node_id for s in dist_steps] if dist_steps else []

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([c.header_label for c in cols])

        for node_id in mapped_node_ids:
            step = step_by_node.get(node_id)
            row = [self._resolve(c, run, deal, step, col_to_node) for c in cols]
            writer.writerow(row)

        return out.getvalue()

    def _resolve(
        self,
        col: GlobalExportColumn,
        run: ProcessingRun,
        deal: Deal | None,
        step: ExecutionStep | None,
        col_to_node: dict[int, int],
    ) -> str:
        if col.value_type == "distribution_node":
            node_id = col_to_node.get(col.id)
            if node_id and step and step.node_id == node_id:
                value = step.result or Decimal("0")
            elif node_id:
                # Resolve from a different step (the mapped node)
                mapped_step = (
                    self.db.query(ExecutionStep)
                    .filter(ExecutionStep.run_id == run.id, ExecutionStep.node_id == node_id)
                    .first()
                )
                value = mapped_step.result if mapped_step and mapped_step.result else Decimal("0")
            else:
                value = step.result if step and step.result else Decimal("0")
            if col.prorate_by:
                value = self._apply_prorate(value, col, run)
            return self._format(value, col)

        if col.value_type == "literal":
            return col.literal_value or ""

        if col.value_type == "run_meta":
            if col.meta_field == "run_code":
                return f"RUN-{run.id}"
            if col.meta_field in ("payment_date", "report_period"):
                return run.report_period or ""
            return ""

        if col.value_type == "deal_meta":
            if not deal:
                return ""
            if col.meta_field == "deal_id":
                return deal.name.replace(" ", "_") if deal.name else f"deal_{deal.id}"
            if col.meta_field == "deal_name":
                return deal.name
            if col.meta_field == "product_type":
                return deal.product_type or ""
            return ""

        return ""

    def _apply_prorate(self, value: Decimal, col: GlobalExportColumn, run: ProcessingRun) -> Decimal:
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
        if col.prorate_by == "regs":
            return value * (bal_regs / total)
        return value

    @staticmethod
    def _format(value: Decimal | None, col: GlobalExportColumn) -> str:
        if value is None:
            return ""
        if col.format_type == "decimal" and isinstance(value, Decimal):
            places = col.decimal_places or 2
            return f"{value:.{places}f}"
        if col.format_type == "integer" and isinstance(value, Decimal):
            return f"{int(value)}"
        return str(value)

    @staticmethod
    def _placeholder(col: GlobalExportColumn) -> str:
        if col.value_type == "distribution_node":
            return "0.00"
        if col.value_type == "literal":
            return col.literal_value or ""
        if col.value_type == "run_meta":
            return f"<{col.meta_field or 'meta'}>"
        if col.value_type == "deal_meta":
            return f"<{col.meta_field or 'meta'}>"
        return ""
