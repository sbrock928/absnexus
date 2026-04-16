"""Variable service with 3-tier scope resolution."""
from sqlalchemy.orm import Session
from app.models.deal import Deal
from app.models.variable import VariableDefinition
from app.variables.dao import VariableDAO


class VariableService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dao = VariableDAO(db)

    def resolve(self, name: str, deal: Deal) -> VariableDefinition | None:
        """Resolve variable: deal -> servicer -> system."""
        v = self.dao.find_by_name_and_scope(name, "deal", deal_id=deal.id)
        if v:
            return v
        v = self.dao.find_by_name_and_scope(name, "servicer", servicer_id=deal.servicer_id)
        if v:
            return v
        return self.dao.find_by_name_and_scope(name, "system")

    def list_available_for_deal(self, deal: Deal) -> list[VariableDefinition]:
        """Merge all tiers with deal > servicer > system override semantics."""
        system_vars = {v.name: v for v in self.dao.list_system()}
        servicer_vars = {v.name: v for v in self.dao.list_for_servicer(deal.servicer_id)}
        deal_vars = {v.name: v for v in self.dao.list_for_deal(deal.id)}
        merged = {**system_vars, **servicer_vars, **deal_vars}
        return sorted(merged.values(), key=lambda v: v.name)
