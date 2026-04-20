"""Tranche service unit tests."""

from decimal import Decimal
from app.tranches.service import TrancheService
from app.tranches.dao import TrancheDAO
from app.models.servicer import Servicer
from app.models.deal import Deal
from app.models.tranche import DealTranche


def _make_deal(db):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    d = Deal(name="TEST", servicer_id=1, created_by="t")
    db.add(d)
    db.flush()
    return d


def test_build_context_combined(db):
    deal = _make_deal(db)
    dao = TrancheDAO(db)
    t = dao.create(
        deal_id=deal.id, class_label="A", regulation_type="combined", note_rate=Decimal("0.0425")
    )
    dao.set_balance(t.id, "2026-04", Decimal("182255600"))
    ctx = TrancheService(db).build_tranche_context(deal.id, "2026-04")
    assert ctx["static_class_a_balance"] == Decimal("182255600")
    assert ctx["static_class_a_note_rate"] == Decimal("0.0425")


def test_build_context_with_split(db):
    deal = _make_deal(db)
    dao = TrancheDAO(db)
    t144 = dao.create(
        deal_id=deal.id, class_label="A", regulation_type="144a", note_rate=Decimal("0.0425")
    )
    tregs = dao.create(
        deal_id=deal.id, class_label="A", regulation_type="regs", note_rate=Decimal("0.0425")
    )
    dao.set_balance(t144.id, "2026-04", Decimal("100000000"))
    dao.set_balance(tregs.id, "2026-04", Decimal("82255600"))
    ctx = TrancheService(db).build_tranche_context(deal.id, "2026-04")
    assert ctx["static_class_a_balance"] == Decimal("182255600")
    assert ctx["static_class_a_balance_144a"] == Decimal("100000000")
    assert ctx["static_class_a_balance_regs"] == Decimal("82255600")


def test_build_context_prior_month(db):
    deal = _make_deal(db)
    dao = TrancheDAO(db)
    t = dao.create(deal_id=deal.id, class_label="A", regulation_type="combined")
    dao.set_balance(t.id, "2026-04", Decimal("180000000"))
    dao.set_balance(t.id, "2026-03", Decimal("185000000"))
    ctx = TrancheService(db).build_tranche_context(deal.id, "2026-04", "2026-03")
    assert ctx["static_class_a_balance"] == Decimal("180000000")
    assert ctx["static_class_a_balance_prior"] == Decimal("185000000")
