"""Batch — orchestrates processing across multiple deals."""

import json
import time
import zipfile
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from sqlalchemy.orm import Session

from app.batch.dao import BatchDAO
from app.models.batch import BatchRun
from app.models.deal import Deal
from app.models.processing import ProcessingRun, ExecutionStep
from app.services.tape_extractor import TapeExtractor
from app.services.dag_executor import DagExecutor


class DealTapeInput:
    """Input for a single deal in a batch run."""

    def __init__(
        self,
        deal_id: int,
        source_filename: str,
        source_file_path: str,
        source_file_hash: str,
    ) -> None:
        self.deal_id = deal_id
        self.source_filename = source_filename
        self.source_file_path = source_file_path
        self.source_file_hash = source_file_hash


class BatchService:
    def __init__(self, db: Session) -> None:
        self.dao = BatchDAO(db)
        self.db = db

    def get(self, batch_id: int) -> BatchRun | None:
        return self.dao.get(batch_id)

    def list_recent(self, limit: int = 20) -> list[BatchRun]:
        return self.dao.list_recent(limit)

    def list_runs(self, batch_id: int) -> list[ProcessingRun]:
        return self.dao.list_runs_for_batch(batch_id)

    def create_batch(
        self,
        period: str,
        username: str,
        deal_inputs: list[DealTapeInput],
    ) -> BatchRun:
        """Create a new batch and its child ProcessingRuns in 'pending' status."""
        batch = BatchRun(
            batch_code=self.dao.next_batch_code(period),
            report_period=period,
            status="pending",
            deals_total=len(deal_inputs),
            started_by=username,
        )
        self.dao.create(batch)

        for di in deal_inputs:
            run = ProcessingRun(
                deal_id=di.deal_id,
                report_period=period,
                status="pending",
                tape_file_path=di.source_file_path,
                tape_file_hash=di.source_file_hash,
                created_by=username,
                batch_id=batch.id,
            )
            self.db.add(run)

        self.db.flush()
        return batch

    def execute_batch(self, batch: BatchRun) -> BatchRun:
        """Run all deals in the batch sequentially.

        For each deal: extract -> execute -> export. Failures don't stop the
        batch — they just mark that deal as failed and move on.
        """
        if batch.status != "pending":
            raise ValueError(f"Cannot execute batch in status '{batch.status}'.")

        batch.status = "running"
        batch.started_at = datetime.utcnow()
        start = time.time()

        runs = self.dao.list_runs_for_batch(batch.id)
        errors: list[str] = []

        for run in runs:
            try:
                self._execute_single(run)
            except Exception as exc:
                run.status = "failed"
                run.error_message = str(exc)[:500]
                errors.append(f"Deal {run.deal_id}: {exc}")
                batch.deals_failed += 1
                self.db.flush()
                continue

            if run.status == "completed":
                batch.deals_completed += 1
            elif run.status == "failed":
                batch.deals_failed += 1

            self.db.flush()

        # Finalize
        batch.completed_at = datetime.utcnow()
        batch.execution_time_ms = int((time.time() - start) * 1000)
        if errors:
            batch.error_summary = json.dumps(errors)

        if batch.deals_failed == 0:
            batch.status = "completed"
        elif batch.deals_completed == 0:
            batch.status = "failed"
        else:
            batch.status = "completed_with_errors"

        self.db.flush()
        return batch

    def _execute_single(self, run: ProcessingRun) -> None:
        """Execute extract + execute + export for one deal."""
        # Extract
        if run.status == "pending":
            if not run.tape_file_path:
                raise ValueError("No tape uploaded for this run.")
            run.status = "extracting"
            self.db.flush()
            extractor = TapeExtractor(self.db)
            extractor.extract_all(run, run.tape_file_path)
            run.status = "extracted"
            self.db.flush()

        if run.status != "extracted":
            return  # extraction failed

        # Execute DAG
        run.status = "executing"
        self.db.flush()
        executor = DagExecutor(self.db)
        result = executor.execute(run)

        if result.errors:
            run.status = "failed"
            run.error_message = "; ".join(result.errors[:5])
        else:
            run.status = "executed"

        run.total_distribution = result.distribution_total
        run.validations_passed = result.validations_passed
        run.validations_total = result.validations_total
        self.db.flush()

        if run.status != "executed":
            return  # execution failed

        # Export CSV (best effort — don't fail batch if export fails)
        try:
            from app.services.export_service import ExportService

            path, file_hash = ExportService(self.db).generate_csv(run, template_id=1)
            run.export_file_path = path
            run.export_file_hash = file_hash
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            self.db.flush()
        except Exception:
            # Export failure doesn't fail the run — mark as completed anyway
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            self.db.flush()

    def get_batch_summary(self, batch_id: int) -> dict:
        """Build summary dict for the batch results page."""
        batch = self.dao.get(batch_id)
        if batch is None:
            raise ValueError("Batch not found.")

        runs = self.dao.list_runs_for_batch(batch_id)

        # Aggregate totals
        total_dist = Decimal("0")
        total_nodes = 0
        total_validations_passed = 0
        total_validations_failed = 0
        exports_ready = 0

        per_deal: list[dict] = []
        for run in runs:
            deal = self.db.query(Deal).filter(Deal.id == run.deal_id).first()
            if run.total_distribution:
                total_dist += run.total_distribution

            v_passed = run.validations_passed or 0
            v_total = run.validations_total or 0
            v_failed = v_total - v_passed
            total_validations_passed += v_passed
            total_validations_failed += v_failed

            # Get execution steps for this run
            exec_steps = (
                self.db.query(ExecutionStep)
                .filter(ExecutionStep.run_id == run.id)
                .order_by(ExecutionStep.step_order)
                .all()
            )
            node_count = len(exec_steps)
            total_nodes += node_count

            if run.export_file_path:
                exports_ready += 1

            distributions = [s for s in exec_steps if s.node_type == "distribution"]
            validations = [s for s in exec_steps if s.node_type == "validation"]

            per_deal.append(
                {
                    "run_id": run.id,
                    "run_code": f"RUN-{run.id}",
                    "deal_id": run.deal_id,
                    "deal_name": deal.name if deal else f"Deal {run.deal_id}",
                    "status": run.status,
                    "nodes_executed": node_count,
                    "execution_time_ms": None,
                    "total_distribution": (
                        str(run.total_distribution) if run.total_distribution else "0"
                    ),
                    "validations_passed": v_passed,
                    "validations_failed": v_failed,
                    "has_export": bool(run.export_file_path),
                    "distributions": [
                        {
                            "field_code": d.export_field or "",
                            "payment_type": d.payment_type or "",
                            "amount": str(d.result) if d.result else "0",
                        }
                        for d in distributions
                    ],
                    "validations": [
                        {
                            "node_key": v.node_key,
                            "node_name": v.node_name,
                            "passed": v.passed == 1,
                            "difference": str(v.difference) if v.difference else "0",
                        }
                        for v in validations
                    ],
                    "first_failed_validation": next(
                        (
                            {
                                "node_key": v.node_key,
                                "node_name": v.node_name,
                                "difference": str(v.difference) if v.difference else "0",
                            }
                            for v in validations
                            if v.passed == 0
                        ),
                        None,
                    ),
                }
            )

        return {
            "batch_id": batch.id,
            "batch_code": batch.batch_code,
            "report_period": batch.report_period,
            "status": batch.status,
            "deals_total": batch.deals_total,
            "deals_completed": batch.deals_completed,
            "deals_failed": batch.deals_failed,
            "total_distribution": str(total_dist),
            "total_nodes": total_nodes,
            "validations_passed": total_validations_passed,
            "validations_failed": total_validations_failed,
            "exports_ready": exports_ready,
            "execution_time_ms": batch.execution_time_ms,
            "started_by": batch.started_by,
            "started_at": batch.started_at.isoformat() if batch.started_at else None,
            "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            "deals": per_deal,
        }

    def generate_batch_zip(self, batch_id: int) -> BytesIO:
        """Zip all CSV exports from a batch into a single download."""
        runs = self.dao.list_runs_for_batch(batch_id)

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for run in runs:
                if not run.export_file_path:
                    continue
                path = Path(run.export_file_path)
                if not path.exists():
                    continue
                arcname = f"deal_{run.deal_id}_{run.report_period}.csv"
                zf.write(path, arcname=arcname)

        buffer.seek(0)
        return buffer
