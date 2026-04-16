"""Variable data access."""

from sqlalchemy.orm import Session
from app.models.variable import VariableDefinition, VariableAlias


class VariableDAO:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> VariableDefinition:
        var = VariableDefinition(**kwargs)
        self.db.add(var)
        self.db.flush()
        return var

    def get(self, var_id: int) -> VariableDefinition | None:
        return self.db.query(VariableDefinition).filter(VariableDefinition.id == var_id).first()

    def list_system(self) -> list[VariableDefinition]:
        return (
            self.db.query(VariableDefinition)
            .filter(VariableDefinition.scope == "system")
            .order_by(VariableDefinition.name)
            .all()
        )

    def list_for_servicer(self, servicer_id: int) -> list[VariableDefinition]:
        return (
            self.db.query(VariableDefinition)
            .filter(
                VariableDefinition.scope == "servicer",
                VariableDefinition.servicer_id == servicer_id,
            )
            .order_by(VariableDefinition.name)
            .all()
        )

    def list_for_deal(self, deal_id: int) -> list[VariableDefinition]:
        return (
            self.db.query(VariableDefinition)
            .filter(
                VariableDefinition.scope == "deal",
                VariableDefinition.deal_id == deal_id,
            )
            .order_by(VariableDefinition.name)
            .all()
        )

    def list_all_servicer(self) -> list[VariableDefinition]:
        """All servicer-scoped variables across all servicers."""
        return (
            self.db.query(VariableDefinition)
            .filter(VariableDefinition.scope == "servicer")
            .order_by(VariableDefinition.name)
            .all()
        )

    def list_all_deal(self) -> list[VariableDefinition]:
        """All deal-scoped variables across all deals."""
        return (
            self.db.query(VariableDefinition)
            .filter(VariableDefinition.scope == "deal")
            .order_by(VariableDefinition.name)
            .all()
        )

    def find_by_name_and_scope(
        self, name: str, scope: str, servicer_id: int | None = None, deal_id: int | None = None
    ) -> VariableDefinition | None:
        q = self.db.query(VariableDefinition).filter(
            VariableDefinition.name == name, VariableDefinition.scope == scope
        )
        if servicer_id is not None:
            q = q.filter(VariableDefinition.servicer_id == servicer_id)
        if deal_id is not None:
            q = q.filter(VariableDefinition.deal_id == deal_id)
        return q.first()

    def update(self, var: VariableDefinition, **kwargs) -> VariableDefinition:
        for k, v in kwargs.items():
            if v is not None:
                setattr(var, k, v)
        self.db.flush()
        return var

    def delete(self, var: VariableDefinition) -> None:
        self.db.delete(var)
        self.db.flush()

    # Aliases
    def set_alias(
        self,
        variable_id: int,
        display_alias: str,
        servicer_id: int | None = None,
        deal_id: int | None = None,
    ) -> VariableAlias:
        existing = (
            self.db.query(VariableAlias)
            .filter(
                VariableAlias.variable_id == variable_id,
                VariableAlias.servicer_id == servicer_id,
                VariableAlias.deal_id == deal_id,
            )
            .first()
        )
        if existing:
            if not display_alias:
                self.db.delete(existing)
                self.db.flush()
                return existing
            existing.display_alias = display_alias
            self.db.flush()
            return existing
        alias = VariableAlias(
            variable_id=variable_id,
            servicer_id=servicer_id,
            deal_id=deal_id,
            display_alias=display_alias,
        )
        self.db.add(alias)
        self.db.flush()
        return alias
