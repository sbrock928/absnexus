"""Deal service unit tests."""
from app.services.deal_service import DealService
from app.models.servicer import Servicer


def test_create_deal(db):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    svc = DealService(db)
    deal = svc.create("TEST-1", 1, "ABS", "tester")
    assert deal.id is not None
    assert deal.name == "TEST-1"


def test_list_deals_filtered(db):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    svc = DealService(db)
    svc.create("D1", 1, "ABS", "t")
    d2 = svc.create("D2", 1, "ABS", "t")
    svc.update(d2, status="active")
    assert len(svc.list_all(status="active")) == 1
    assert len(svc.list_all()) == 2
