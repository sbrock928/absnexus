"""Deal CRUD service."""

from sqlalchemy.orm import Session
from app.models.deal import Deal

VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"active"},
    "active": {"archived"},
    "archived": {"active"},
}


class DealService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, name: str, servicer_id: int, product_type: str, created_by: str) -> Deal:
        deal = Deal(
            name=name,
            servicer_id=servicer_id,
            product_type=product_type,
            created_by=created_by,
        )
        self.db.add(deal)
        self.db.flush()
        return deal

    def list_all(
        self,
        status: str | None = None,
        exclude_status: str | None = None,
    ) -> list[Deal]:
        q = self.db.query(Deal)
        if status:
            q = q.filter(Deal.status == status)
        if exclude_status:
            q = q.filter(Deal.status != exclude_status)
        return q.order_by(Deal.updated_at.desc()).all()

    def get(self, deal_id: int) -> Deal | None:
        return self.db.query(Deal).filter(Deal.id == deal_id).first()

    def update(self, deal: Deal, **kwargs: str | None) -> Deal:
        new_status = kwargs.get("status")
        if new_status is not None and new_status != deal.status:
            allowed = VALID_TRANSITIONS.get(deal.status, set())
            if new_status not in allowed:
                raise ValueError(
                    f"Cannot transition from '{deal.status}' to '{new_status}'. "
                    f"Allowed: {', '.join(sorted(allowed)) if allowed else 'none'}."
                )
        for k, v in kwargs.items():
            if v is not None:
                setattr(deal, k, v)
        self.db.flush()
        return deal

    def delete(self, deal: Deal) -> None:
        self.db.delete(deal)
        self.db.flush()
