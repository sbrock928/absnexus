"""Functional tests for export column routes."""
import pytest


@pytest.fixture()
def deal_id(client, db):
    from app.models.servicer import Servicer
    from app.models.deal import Deal
    s = Servicer(name="Test", short_code="T")
    db.add(s)
    db.flush()
    d = Deal(name="Route Test Deal", servicer_id=s.id, product_type="ABS", created_by="testuser")
    db.add(d)
    db.flush()
    return d.id


class TestColumnRoutes:
    def test_list_empty(self, client, deal_id):
        r = client.get(f"/api/deals/{deal_id}/export-columns")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_column(self, client, deal_id):
        r = client.post(f"/api/deals/{deal_id}/export-columns", json={
            "header_label": "AMOUNT",
            "value_type": "literal",
            "literal_value": "100",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["header_label"] == "AMOUNT"
        assert data["position"] == 1

    def test_update_column(self, client, deal_id):
        r = client.post(f"/api/deals/{deal_id}/export-columns", json={
            "header_label": "OLD",
            "value_type": "literal",
            "literal_value": "x",
        })
        col_id = r.json()["id"]
        r2 = client.patch(f"/api/export-columns/{col_id}", json={
            "header_label": "NEW",
        })
        assert r2.status_code == 200
        assert r2.json()["header_label"] == "NEW"

    def test_delete_column(self, client, deal_id):
        r = client.post(f"/api/deals/{deal_id}/export-columns", json={
            "header_label": "DEL",
            "value_type": "literal",
            "literal_value": "x",
        })
        col_id = r.json()["id"]
        r2 = client.delete(f"/api/export-columns/{col_id}")
        assert r2.status_code == 204

        r3 = client.get(f"/api/deals/{deal_id}/export-columns")
        assert r3.json() == []

    def test_copy_preset(self, client, deal_id):
        r = client.post(f"/api/deals/{deal_id}/export-columns/copy-preset", json={
            "preset_key": "system_a",
        })
        assert r.status_code == 200
        assert len(r.json()) == 7
        assert r.json()[0]["header_label"] == "DEAL_ID"

    def test_reorder_columns(self, client, deal_id):
        ids = []
        for label in ["A", "B", "C"]:
            r = client.post(f"/api/deals/{deal_id}/export-columns", json={
                "header_label": label,
                "value_type": "literal",
                "literal_value": label.lower(),
            })
            ids.append(r.json()["id"])

        r = client.post(f"/api/deals/{deal_id}/export-columns/reorder", json={
            "ordered_column_ids": [ids[2], ids[0], ids[1]],
        })
        assert r.status_code == 200
        labels = [c["header_label"] for c in r.json()]
        assert labels == ["C", "A", "B"]


class TestPresetRoutes:
    def test_list_presets(self, client):
        r = client.get("/api/export-presets")
        assert r.status_code == 200
        keys = [p["key"] for p in r.json()]
        assert "system_a" in keys
        assert "system_b" in keys
        assert "system_c" in keys


class TestPreviewRoutes:
    def test_preview_empty(self, client, deal_id):
        r = client.get(f"/api/deals/{deal_id}/export-preview")
        assert r.status_code == 200
        assert r.json()["row_count"] == 0

    def test_preview_with_columns(self, client, deal_id):
        client.post(f"/api/deals/{deal_id}/export-columns", json={
            "header_label": "TEST",
            "value_type": "literal",
            "literal_value": "hello",
        })
        r = client.get(f"/api/deals/{deal_id}/export-preview")
        assert r.status_code == 200
        assert r.json()["row_count"] == 2  # 2 sample rows
        assert "TEST" in r.json()["csv"]
