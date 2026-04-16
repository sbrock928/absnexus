"""Tranche service — balance management and context building."""
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.tranche import DealTranche
from app.tranches.dao import TrancheDAO


class TrancheService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dao = TrancheDAO(db)

    def build_tranche_context(self, deal_id: int, period: str, prior_period: str | None = None) -> dict[str, Decimal]:
        """Build deterministic formula variables from tranches.

        Returns keys like: class_a_balance, class_a_note_rate,
        class_a_balance_144a, class_a_balance_prior, etc.
        """
        tranches = self.dao.list_for_deal(deal_id)
        context: dict[str, Decimal] = {}

        # Group by class label to combine 144A/RegS
        by_class: dict[str, list[DealTranche]] = {}
        for t in tranches:
            by_class.setdefault(t.class_label.lower(), []).append(t)

        for label, class_tranches in by_class.items():
            prefix = f"class_{label}"
            combined_balance = Decimal("0")
            combined_prior = Decimal("0")

            for t in class_tranches:
                bal = self.dao.get_balance(t.id, period)
                balance = bal.balance if bal else Decimal("0")

                if t.regulation_type == "144a":
                    context[f"{prefix}_balance_144a"] = balance
                elif t.regulation_type == "regs":
                    context[f"{prefix}_balance_regs"] = balance
                combined_balance += balance

                # Prior period
                if prior_period:
                    prior_bal = self.dao.get_balance(t.id, prior_period)
                    prior_balance = prior_bal.balance if prior_bal else Decimal("0")
                    if t.regulation_type == "144a":
                        context[f"{prefix}_balance_144a_prior"] = prior_balance
                    elif t.regulation_type == "regs":
                        context[f"{prefix}_balance_regs_prior"] = prior_balance
                    combined_prior += prior_balance

                # Note rate and original balance from first tranche in group
                if t.note_rate is not None and f"{prefix}_note_rate" not in context:
                    context[f"{prefix}_note_rate"] = t.note_rate
                if t.original_balance is not None and f"{prefix}_original_balance" not in context:
                    context[f"{prefix}_original_balance"] = t.original_balance

            context[f"{prefix}_balance"] = combined_balance
            if prior_period:
                context[f"{prefix}_balance_prior"] = combined_prior

        return context
