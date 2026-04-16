"""Export service — generate CSV payment files from distribution nodes."""

import csv
import hashlib
import io
import os
from sqlalchemy.orm import Session

from app.models.processing import ProcessingRun, ExecutionStep
from app.models.export import ExportTemplate, ExportTemplateColumn, ExportFieldMapping
from app.models.deal import Deal
from app.core import settings


class ExportService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_csv(self, run: ProcessingRun, template_id: int) -> tuple[str, str]:
        """Generate CSV and store it. Returns (file_path, sha256_hash)."""
        template = self.db.query(ExportTemplate).filter(ExportTemplate.id == template_id).first()
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Check waterfall reconciliation before allowing export
        from app.processing.service import ProcessingService

        try:
            waterfall = ProcessingService(self.db).get_waterfall(run.id)
        except ValueError:
            waterfall = None

        if waterfall and waterfall["has_tape_value"] and waterfall["reconciled"] is False:
            raise ValueError(
                f"Waterfall reconciliation failed. Calculated remainder "
                f"${waterfall['final_calculated_remainder']} does not match tape "
                f"value ${waterfall['tape_ending_balance']} (diff "
                f"${waterfall['difference']} exceeds tolerance "
                f"${waterfall['tolerance']}). Review distribution amounts before exporting."
            )

        deal = self.db.query(Deal).filter(Deal.id == run.deal_id).first()
        rows = self._build_rows(run, template)

        columns = (
            self.db.query(ExportTemplateColumn)
            .filter(ExportTemplateColumn.template_id == template_id)
            .order_by(ExportTemplateColumn.column_order)
            .all()
        )
        col_names = [c.column_name for c in columns]

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=col_names)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

        content = buf.getvalue()
        file_hash = hashlib.sha256(content.encode()).hexdigest()

        # Store file
        deal_name = deal.name.replace(" ", "_") if deal else "unknown"
        filename = f"{deal_name}_DIST_{run.report_period.replace('-', '')}.csv"
        dest_dir = os.path.join(settings.export_directory, str(run.deal_id), run.report_period)
        os.makedirs(dest_dir, exist_ok=True)
        file_path = os.path.join(dest_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        run.export_file_path = file_path
        run.export_file_hash = file_hash
        self.db.flush()

        return file_path, file_hash

    def preview(self, run_id: int, template_id: int) -> list[dict]:
        """Preview export rows without writing file."""
        run = self.db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
        if not run:
            return []
        template = self.db.query(ExportTemplate).filter(ExportTemplate.id == template_id).first()
        if not template:
            return []
        return self._build_rows(run, template)

    def _build_rows(self, run: ProcessingRun, template: ExportTemplate) -> list[dict]:
        """Build export rows from distribution execution steps."""
        deal = self.db.query(Deal).filter(Deal.id == run.deal_id).first()

        # Get distribution steps only
        dist_steps = (
            self.db.query(ExecutionStep)
            .filter(
                ExecutionStep.run_id == run.id,
                ExecutionStep.node_type == "distribution",
            )
            .order_by(ExecutionStep.step_order)
            .all()
        )

        # Get field mappings for this deal+template
        mappings = (
            self.db.query(ExportFieldMapping)
            .filter(
                ExportFieldMapping.deal_id == run.deal_id,
                ExportFieldMapping.template_id == template.id,
            )
            .all()
        )
        key_to_mapping = {m.node_key: m for m in mappings}

        rows = []
        period_str = run.report_period
        deal_name = deal.name if deal else ""

        if template.format_type == "row_per_payment":
            for step in dist_steps:
                mapping = key_to_mapping.get(step.node_key)
                field_code = (
                    mapping.field_code if mapping else (step.export_field or step.node_key)
                )
                pmt_type = mapping.payment_type if mapping else (step.payment_type or "")
                tranche = mapping.tranche_class if mapping else ""

                rows.append(
                    {
                        "DEAL_ID": deal_name,
                        "PAYMENT_DATE": period_str,
                        "PAYMENT_TYPE": pmt_type.upper() if pmt_type else "",
                        "CLASS": tranche or "",
                        "FIELD_CODE": field_code,
                        "AMOUNT": str(step.result or 0),
                        "RUN_ID": f"RUN-{run.id}",
                    }
                )

        return rows
