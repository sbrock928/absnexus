"""Mapping data access."""

from sqlalchemy.orm import Session
from app.models.variable_mapping import VariableMapping


class MappingDAO:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, deal_id: int, **kwargs) -> VariableMapping:
        m = VariableMapping(deal_id=deal_id, **kwargs)
        self.db.add(m)
        self.db.flush()
        return m

    def get(self, mapping_id: int) -> VariableMapping | None:
        return self.db.query(VariableMapping).filter(VariableMapping.id == mapping_id).first()

    def list_for_deal(self, deal_id: int) -> list[VariableMapping]:
        return (
            self.db.query(VariableMapping)
            .filter(VariableMapping.deal_id == deal_id)
            .order_by(VariableMapping.sheet_name, VariableMapping.row_number)
            .all()
        )

    def update(self, m: VariableMapping, **kwargs) -> VariableMapping:
        for k, v in kwargs.items():
            if v is not None:
                setattr(m, k, v)
        self.db.flush()
        return m

    def delete(self, m: VariableMapping) -> None:
        self.db.delete(m)
        self.db.flush()

    def get_for_variable(self, deal_id: int, variable_id: int) -> VariableMapping | None:
        return (
            self.db.query(VariableMapping)
            .filter(
                VariableMapping.deal_id == deal_id,
                VariableMapping.variable_id == variable_id,
            )
            .first()
        )
