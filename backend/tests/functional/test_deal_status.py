"""Functional tests for deal status transitions and permission guards."""
from app.models.deal import Deal
from app.models.user import User
from app.models.variable_mapping import VariableMapping


def _make_deal(db, name="Test Deal", status="draft"):
    """Create a deal with a seeded servicer."""
    from app.models.servicer import Servicer
    svc = db.query(Servicer).first()
    if not svc:
        svc = Servicer(name="TestSvc", short_code="TS")
        db.add(svc)
        db.flush()
    d = Deal(name=name, servicer_id=svc.id, product_type="ABS Auto", status=status, created_by="testuser")
    db.add(d)
    db.flush()
    return d


# ── Status transitions ──────────────────────────────────────────


def test_valid_transition_draft_to_active(client, db):
    deal = _make_deal(db, status="draft")
    r = client.patch(f"/api/deals/{deal.id}", json={"status": "active"})
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_valid_transition_active_to_archived(client, db):
    deal = _make_deal(db, status="active")
    r = client.patch(f"/api/deals/{deal.id}", json={"status": "archived"})
    assert r.status_code == 200
    assert r.json()["status"] == "archived"


def test_valid_transition_archived_to_active(client, db):
    deal = _make_deal(db, status="archived")
    r = client.patch(f"/api/deals/{deal.id}", json={"status": "active"})
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_invalid_transition_draft_to_archived(client, db):
    deal = _make_deal(db, status="draft")
    r = client.patch(f"/api/deals/{deal.id}", json={"status": "archived"})
    assert r.status_code == 400
    assert "Cannot transition" in r.json()["detail"]


def test_invalid_transition_active_to_draft(client, db):
    deal = _make_deal(db, status="active")
    r = client.patch(f"/api/deals/{deal.id}", json={"status": "draft"})
    assert r.status_code == 400


def test_invalid_transition_archived_to_draft(client, db):
    deal = _make_deal(db, status="archived")
    r = client.patch(f"/api/deals/{deal.id}", json={"status": "draft"})
    assert r.status_code == 400


def test_same_status_is_allowed(client, db):
    deal = _make_deal(db, status="active")
    r = client.patch(f"/api/deals/{deal.id}", json={"status": "active"})
    assert r.status_code == 200


# ── Archived deal edit block ────────────────────────────────────


def test_archived_deal_blocks_mapping_create(client, db):
    deal = _make_deal(db, status="archived")
    r = client.post(f"/api/deals/{deal.id}/mappings", json={
        "variable_id": 1, "sheet_name": "Sheet1", "column_letter": "A", "row_number": 1,
    })
    assert r.status_code == 403
    assert "archived" in r.json()["detail"].lower()


def test_archived_deal_blocks_dag_save(client, db):
    deal = _make_deal(db, status="archived")
    r = client.post(f"/api/deals/{deal.id}/dag", json={"nodes": [], "edges": []})
    assert r.status_code == 403


def test_archived_deal_blocks_tranche_create(client, db):
    deal = _make_deal(db, status="archived")
    r = client.post(f"/api/deals/{deal.id}/tranches", json={
        "class_label": "A", "cusip": "TEST123", "note_rate": "0.05",
    })
    assert r.status_code == 403


def test_active_deal_allows_mapping_create(client, db):
    from app.models.variable import VariableDefinition
    v = VariableDefinition(name="test_var", display_name="Test", scope="system", data_type="decimal")
    db.add(v)
    db.flush()
    deal = _make_deal(db, status="active")
    r = client.post(f"/api/deals/{deal.id}/mappings", json={
        "variable_id": v.id, "sheet_name": "Sheet1", "column_letter": "A", "row_number": 1,
    })
    assert r.status_code == 201


def test_draft_deal_allows_edits(client, db):
    deal = _make_deal(db, status="draft")
    r = client.post(f"/api/deals/{deal.id}/dag", json={"nodes": [], "edges": []})
    # Should not be blocked — draft is editable
    assert r.status_code != 403


# ── Processing guards ───────────────────────────────────────────


def test_analyst_cannot_process_draft_deal(analyst_client, db):
    deal = _make_deal(db, status="draft")
    r = analyst_client.post(f"/api/deals/{deal.id}/runs", json={"report_period": "2026-04"})
    assert r.status_code == 403
    assert "active" in r.json()["detail"].lower()


def test_analyst_cannot_process_archived_deal(analyst_client, db):
    deal = _make_deal(db, status="archived")
    r = analyst_client.post(f"/api/deals/{deal.id}/runs", json={"report_period": "2026-04"})
    assert r.status_code == 403


def test_analyst_can_process_active_deal(analyst_client, db):
    deal = _make_deal(db, status="active")
    r = analyst_client.post(f"/api/deals/{deal.id}/runs", json={"report_period": "2026-04"})
    assert r.status_code == 201


def test_analytics_can_process_draft_deal(client, db):
    deal = _make_deal(db, status="draft")
    r = client.post(f"/api/deals/{deal.id}/runs", json={"report_period": "2026-04"})
    assert r.status_code == 201


def test_analytics_can_process_archived_deal(client, db):
    deal = _make_deal(db, status="archived")
    r = client.post(f"/api/deals/{deal.id}/runs", json={"report_period": "2026-04"})
    assert r.status_code == 201


# ── exclude_status query param ──────────────────────────────────


def test_exclude_status_filter(client, db):
    _make_deal(db, name="Draft Deal", status="draft")
    _make_deal(db, name="Active Deal", status="active")

    r = client.get("/api/deals/?exclude_status=draft")
    assert r.status_code == 200
    names = [d["name"] for d in r.json()]
    assert "Active Deal" in names
    assert "Draft Deal" not in names
