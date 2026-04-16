"""Prior month context service."""

from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.processing import ProcessingRun, ExtractedValue, ExecutionStep
from app.models.dag import DagNode, DagVersion


class PriorMonthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_prior_run(self, deal_id: int, current_period: str) -> ProcessingRun | None:
        """Find the completed run from the prior calendar month."""
        prior_period = self._prior_calendar_month(current_period)
        return (
            self.db.query(ProcessingRun)
            .filter(
                ProcessingRun.deal_id == deal_id,
                ProcessingRun.report_period == prior_period,
                ProcessingRun.status == "completed",
            )
            .order_by(ProcessingRun.created_at.desc())
            .first()
        )

    def build_prior_context(self, prior_run_id: int) -> dict[str, Decimal]:
        """Load all results from prior run with _prior suffix."""
        context: dict[str, Decimal] = {}
        # Tape values
        for ev in (
            self.db.query(ExtractedValue).filter(ExtractedValue.run_id == prior_run_id).all()
        ):
            if ev.parsed_value is not None:
                context[f"{ev.variable_name}_prior"] = ev.parsed_value
        # Execution steps
        for step in (
            self.db.query(ExecutionStep).filter(ExecutionStep.run_id == prior_run_id).all()
        ):
            if step.result is not None:
                context[f"{step.node_key}_prior"] = step.result
        return context

    def get_default_priors(self, deal_id: int) -> dict[str, Decimal]:
        """For first month — load default_prior_value from dag nodes."""
        current_version = (
            self.db.query(DagVersion)
            .filter(DagVersion.deal_id == deal_id, DagVersion.is_current == 1)
            .first()
        )
        if not current_version:
            return {}
        nodes = (
            self.db.query(DagNode)
            .filter(
                DagNode.dag_version_id == current_version.id,
                DagNode.default_prior_value.isnot(None),
            )
            .all()
        )
        return {f"{n.key}_prior": n.default_prior_value for n in nodes}

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
