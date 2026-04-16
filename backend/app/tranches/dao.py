"""Tranche data access."""

from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.tranche import DealTranche, TrancheBalance


class TrancheDAO:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, deal_id: int, **kwargs) -> DealTranche:
        t = DealTranche(deal_id=deal_id, **kwargs)
        self.db.add(t)
        self.db.flush()
        return t

    def get(self, tranche_id: int) -> DealTranche | None:
        return self.db.query(DealTranche).filter(DealTranche.id == tranche_id).first()

    def list_for_deal(self, deal_id: int) -> list[DealTranche]:
        return (
            self.db.query(DealTranche)
            .filter(DealTranche.deal_id == deal_id, DealTranche.is_active == 1)
            .order_by(DealTranche.class_label)
            .all()
        )

    def update(self, t: DealTranche, **kwargs) -> DealTranche:
        for k, v in kwargs.items():
            if v is not None:
                setattr(t, k, v)
        self.db.flush()
        return t

    def set_balance(
        self, tranche_id: int, period: str, balance: Decimal, source: str = "manual"
    ) -> TrancheBalance:
        existing = (
            self.db.query(TrancheBalance)
            .filter(TrancheBalance.tranche_id == tranche_id, TrancheBalance.period == period)
            .first()
        )
        if existing:
            existing.balance = balance
            existing.source = source
            self.db.flush()
            return existing
        tb = TrancheBalance(tranche_id=tranche_id, period=period, balance=balance, source=source)
        self.db.add(tb)
        self.db.flush()
        return tb

    def get_balance(self, tranche_id: int, period: str) -> TrancheBalance | None:
        return (
            self.db.query(TrancheBalance)
            .filter(TrancheBalance.tranche_id == tranche_id, TrancheBalance.period == period)
            .first()
        )

    def list_balances(self, tranche_id: int) -> list[TrancheBalance]:
        return (
            self.db.query(TrancheBalance)
            .filter(TrancheBalance.tranche_id == tranche_id)
            .order_by(TrancheBalance.period.desc())
            .all()
        )
