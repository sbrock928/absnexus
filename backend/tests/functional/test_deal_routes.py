"""Deal route functional tests."""

from app.models.servicer import Servicer


def test_create_deal(client, db, test_servicer):
    r = client.post("/api/deals/", json={"name": "TEST-1", "servicer_id": test_servicer.id})
    assert r.status_code == 201
    assert r.json()["name"] == "TEST-1"


def test_list_deals(client, db, test_servicer):
    client.post("/api/deals/", json={"name": "D1", "servicer_id": test_servicer.id})
    client.post("/api/deals/", json={"name": "D2", "servicer_id": test_servicer.id})
    r = client.get("/api/deals/")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_deal(client, db, test_deal):
    r = client.get(f"/api/deals/{test_deal.id}")
    assert r.status_code == 200
    assert r.json()["name"] == "AMORT 2024-1"


def test_update_deal(client, db, test_deal):
    r = client.patch(f"/api/deals/{test_deal.id}", json={"status": "active"})
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_deal_not_found(client):
    r = client.get("/api/deals/9999")
    assert r.status_code == 404
