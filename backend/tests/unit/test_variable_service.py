"""Variable service unit tests — 3-tier resolution."""
from app.variables.service import VariableService
from app.variables.dao import VariableDAO
from app.models.variable import VariableDefinition
from app.models.servicer import Servicer
from app.models.deal import Deal


def test_resolve_system(db):
    db.add(VariableDefinition(name="oc_floor", scope="system"))
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    deal = Deal(name="D1", servicer_id=1, created_by="t")
    db.add(deal)
    db.flush()
    v = VariableService(db).resolve("oc_floor", deal)
    assert v is not None
    assert v.scope == "system"


def test_servicer_overrides_system(db):
    db.add(VariableDefinition(name="oc_floor", scope="system"))
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    db.add(VariableDefinition(name="oc_floor", scope="servicer", servicer_id=1))
    deal = Deal(name="D1", servicer_id=1, created_by="t")
    db.add(deal)
    db.flush()
    v = VariableService(db).resolve("oc_floor", deal)
    assert v.scope == "servicer"


def test_deal_overrides_servicer(db):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    deal = Deal(name="D1", servicer_id=1, created_by="t")
    db.add(deal)
    db.flush()
    db.add(VariableDefinition(name="oc_floor", scope="system"))
    db.add(VariableDefinition(name="oc_floor", scope="servicer", servicer_id=1))
    db.add(VariableDefinition(name="oc_floor", scope="deal", deal_id=deal.id))
    db.flush()
    v = VariableService(db).resolve("oc_floor", deal)
    assert v.scope == "deal"


def test_list_available_merges(db):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    deal = Deal(name="D1", servicer_id=1, created_by="t")
    db.add(deal)
    db.flush()
    db.add(VariableDefinition(name="total_collections", scope="system"))
    db.add(VariableDefinition(name="svc_fee_rate", scope="servicer", servicer_id=1))
    db.add(VariableDefinition(name="deal_specific", scope="deal", deal_id=deal.id))
    db.flush()
    available = VariableService(db).list_available_for_deal(deal)
    names = {v.name for v in available}
    assert "total_collections" in names
    assert "svc_fee_rate" in names
    assert "deal_specific" in names
