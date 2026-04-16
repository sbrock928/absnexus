"""Batch — data access layer."""

from sqlalchemy.orm import Session

from app.models.batch import BatchRun
from app.models.processing import ProcessingRun


class BatchDAO:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, batch_id: int) -> BatchRun | None:
        return self.db.query(BatchRun).filter(BatchRun.id == batch_id).first()

    def get_by_code(self, code: str) -> BatchRun | None:
        return self.db.query(BatchRun).filter(BatchRun.batch_code == code).first()

    def list_recent(self, limit: int = 20) -> list[BatchRun]:
        return (
            self.db.query(BatchRun)
            .order_by(BatchRun.created_at.desc())
            .limit(limit)
            .all()
        )  # type: ignore[return-value]

    def list_batches_for_period(self, period: str) -> list[BatchRun]:
        return (
            self.db.query(BatchRun)
            .filter(BatchRun.report_period == period)
            .order_by(BatchRun.created_at.desc())
            .all()
        )  # type: ignore[return-value]

    def create(self, batch: BatchRun) -> BatchRun:
        self.db.add(batch)
        self.db.flush()
        return batch

    def list_runs_for_batch(self, batch_id: int) -> list[ProcessingRun]:
        return (
            self.db.query(ProcessingRun)
            .filter(ProcessingRun.batch_id == batch_id)
            .order_by(ProcessingRun.id)
            .all()
        )  # type: ignore[return-value]

    def next_batch_code(self, period: str) -> str:
        """Generate BATCH-{period}-{seq}."""
        existing = self.list_batches_for_period(period)
        seq = len(existing) + 1
        return f"BATCH-{period}-{seq:03d}"
