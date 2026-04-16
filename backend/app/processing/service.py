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
            raise ValueError(f"Waterfall requires a completed run. Current status: {run.status}.")

        deal = self.db.query(Deal).filter(Deal.id == run.deal_id).first()
        if deal is None:
            raise ValueError("Deal not found.")

        starting_var = deal.waterfall_starting_var or "total_available_funds"
        ending_var = deal.waterfall_ending_var or "end_available_funds"
        tolerance = deal.waterfall_tolerance or Decimal("0.01")

        # Starting balance — from extracted values
        extracted = self.db.query(ExtractedValue).filter(ExtractedValue.run_id == run.id).all()
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

        # Build steps with comparison data
        steps = []
        running = starting_balance
        comparison_count = 0
        comparison_matched = 0

        for idx, step in enumerate(distributions, start=1):
            amount = step.result or Decimal("0")
            running = running - amount

            # Comparison data (populated by DagExecutor for distribution nodes
            # with comparison_variable set)
            node = nodes_by_id.get(step.node_id)
            tape_value = str(step.comparison_value) if step.comparison_value is not None else None
            step_diff = str(step.difference) if step.difference is not None else None
            matched = True if step.passed == 1 else (False if step.passed == 0 else None)
            comp_var = node.comparison_variable if node else None

            if tape_value is not None:
                comparison_count += 1
                if matched:
                    comparison_matched += 1

            steps.append(
                {
                    "step": idx,
                    "node_key": step.node_key,
                    "node_name": step.node_name,
                    "amount": str(amount),
                    "remaining_after": str(running),
                    "export_field": step.export_field,
                    "payment_type": step.payment_type,
                    "tape_value": tape_value,
                    "difference": step_diff,
                    "matched": matched,
                    "comparison_variable": comp_var,
                }
            )

        final_remainder = running
        difference = None
        reconciled = None

        if tape_ending_balance is not None:
            difference = abs(final_remainder - tape_ending_balance)
            reconciled = difference <= tolerance

        return {
            "run_id": run.id,
            "run_code": f"RUN-{run.id}",
            "deal_name": deal.name,
            "report_period": run.report_period,
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
            "comparison_count": comparison_count,
            "comparison_matched": comparison_matched,
            "all_compared": comparison_count > 0 and comparison_count == comparison_matched,
        }

    # ── Single-variable re-extraction ──

    def reextract_variable(self, run_id: int, variable_id: int) -> ExtractedValue:
        """Re-read a single variable from the tape for an existing run.

        Used when a user remaps a cell during processing and wants to update
        the extracted value without re-running the entire extraction.
        """
        run = self.db.query(ProcessingRun).filter(ProcessingRun.id == run_id).first()
        if run is None:
            raise ValueError("Run not found.")
        if not run.tape_file_path:
            raise ValueError("No source file on run.")

        from app.mappings.dao import MappingDAO
        from app.variables.dao import VariableDAO
        from app.utils.excel_reader import ExcelReader

        mapping_dao = MappingDAO(self.db)
        mapping = mapping_dao.get_for_variable(run.deal_id, variable_id)
        if mapping is None:
            raise ValueError(f"No mapping for variable {variable_id} on this deal.")

        var_dao = VariableDAO(self.db)
        var = var_dao.get(variable_id)
        var_name = var.name if var else f"var_{variable_id}"

        # Load existing extracted record (if any)
        existing = (
            self.db.query(ExtractedValue)
            .filter(
                ExtractedValue.run_id == run_id,
                ExtractedValue.variable_id == variable_id,
            )
            .first()
        )

        # Re-read the cell
        with ExcelReader(run.tape_file_path) as reader:
            try:
                raw = reader.get_cell_value(
                    mapping.sheet_name,
                    mapping.column_letter,
                    mapping.row_number,
                )
            except (ValueError, KeyError) as exc:
                if existing:
                    existing.warning = f"Failed to read cell: {exc}"
                    self.db.flush()
                    return existing
                raise ValueError(f"Failed to read cell: {exc}") from exc

        cell_ref = f"{mapping.column_letter}{mapping.row_number}"
        if existing:
            ev = existing
            ev.warning = None
        else:
            ev = ExtractedValue(
                run_id=run_id,
                variable_id=variable_id,
                variable_name=var_name,
                data_type=var.data_type if var else "decimal",
            )
            self.db.add(ev)

        ev.sheet_name = mapping.sheet_name
        ev.cell_ref = cell_ref
        ev.raw_value = str(raw) if raw is not None else None

        # Parse
        if raw is None:
            ev.warning = f"Cell {cell_ref} is empty."
            ev.parsed_value = None
        else:
            from app.services.tape_extractor import TapeExtractor

            extractor = TapeExtractor(self.db)
            ev.parsed_value = extractor._parse_value(raw, var.data_type if var else "decimal")

        # Re-compute prior comparison
        if run.prior_run_id and ev.parsed_value is not None:
            prior_ev = (
                self.db.query(ExtractedValue)
                .filter(
                    ExtractedValue.run_id == run.prior_run_id,
                    ExtractedValue.variable_id == variable_id,
                )
                .first()
            )
            if prior_ev and prior_ev.parsed_value is not None:
                ev.prior_value = prior_ev.parsed_value
                if prior_ev.parsed_value != 0:
                    pct = (
                        abs(ev.parsed_value - prior_ev.parsed_value)
                        / abs(prior_ev.parsed_value)
                        * 100
                    )
                    ev.pct_change = pct.quantize(Decimal("0.01"))
                    if pct > 50:
                        ev.warning = f"{var_name} changed by {pct:.1f}% from prior month."

        self.db.flush()
        return ev
