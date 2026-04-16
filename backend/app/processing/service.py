"""Processing service — waterfall balance tracker."""
from decimal import Decimal

from sqlalchemy.orm import Session

from app.dag.dao import DagDAO
from app.models.deal import Deal
from app.models.processing import ProcessingRun, ExtractedValue, ExecutionStep


class ProcessingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_waterfall(self, run_id: int) -> dict:
        """Build the waterfall balance trace for a completed run.

        Walks distribution nodes in waterfall_order (or execution_order
        as fallback), computing running remaining balance after each step.
        Compares final remainder to the deal's configured tape ending variable.
        """
        run = self.db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
        if run is None:
            raise ValueError("Run not found.")

        if run.status not in ("completed", "executed", "failed"):
            raise ValueError(
                f"Waterfall requires a completed run. Current status: {run.status}."
            )

        deal = self.db.query(Deal).filter(Deal.id == run.deal_id).first()
        if deal is None:
            raise ValueError("Deal not found.")

        starting_var = deal.waterfall_starting_var or "total_available_funds"
        ending_var = deal.waterfall_ending_var or "end_available_funds"
        tolerance = deal.waterfall_tolerance or Decimal("0.01")

        # Starting balance — from extracted values
        extracted = (
            self.db.query(ExtractedValue)
            .filter(ExtractedValue.run_id == run.id)
            .all()
        )
        extracted_by_name = {ev.variable_name: ev for ev in extracted}

        starting_ev = extracted_by_name.get(starting_var)
        if starting_ev is None or starting_ev.parsed_value is None:
            raise ValueError(
                f"Starting variable '{starting_var}' not found in extracted values. "
                f"Ensure the deal has a mapping for this tape cell."
            )
        starting_balance = starting_ev.parsed_value

        # Tape-reported ending balance (may not always be reported)
        tape_ending_ev = extracted_by_name.get(ending_var)
        tape_ending_balance = (
            tape_ending_ev.parsed_value
            if tape_ending_ev and tape_ending_ev.parsed_value is not None
            else None
        )

        # Get distribution execution steps
        distributions = (
            self.db.query(ExecutionStep)
            .filter(
                ExecutionStep.run_id == run.id,
                ExecutionStep.node_type == "distribution",
            )
            .order_by(ExecutionStep.step_order)
            .all()
        )
        distributions = [d for d in distributions if d.result is not None]

        # Get DagNode records for waterfall_order
        dag_dao = DagDAO(self.db)
        version = dag_dao.get_current_version(run.deal_id)
        nodes_by_id: dict = {}
        if version:
            for n in dag_dao.get_nodes(version.id):
                nodes_by_id[n.id] = n

        def sort_key(step: ExecutionStep):
            node = nodes_by_id.get(step.node_id)
            explicit_order = getattr(node, "waterfall_order", None) if node else None
            if explicit_order is not None:
                return (0, explicit_order)
            return (1, step.step_order or 0)

        distributions.sort(key=sort_key)

        # Build steps
        steps = []
        running = starting_balance
        for idx, step in enumerate(distributions, start=1):
            amount = step.result or Decimal("0")
            running = running - amount
            steps.append({
                "step": idx,
                "node_key": step.node_key,
                "node_name": step.node_name,
                "amount": str(amount),
                "remaining_after": str(running),
                "export_field": step.export_field,
                "payment_type": step.payment_type,
            })

        final_remainder = running
        difference = None
        reconciled = None

        if tape_ending_balance is not None:
            difference = abs(final_remainder - tape_ending_balance)
            reconciled = difference <= tolerance

        return {
            "run_id": run.id,
            "run_code": f"RUN-{run.id}",
            "starting_var": starting_var,
            "starting_balance": str(starting_balance),
            "ending_var": ending_var,
            "tape_ending_balance": (
                str(tape_ending_balance) if tape_ending_balance is not None else None
            ),
            "tolerance": str(tolerance),
            "steps": steps,
            "step_count": len(steps),
            "final_calculated_remainder": str(final_remainder),
            "difference": str(difference) if difference is not None else None,
            "reconciled": reconciled,
            "has_tape_value": tape_ending_balance is not None,
        }
