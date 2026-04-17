"""Functional tests for global export template and preview routes."""

import pytest

from app.models.global_export import GlobalExportTemplate, GlobalExportColumn


def _seed_template(db, name="My Template"):
    t = GlobalExportTemplate(name=name)
    db.add(t)
    db.flush()
    return t


def _seed_column(db, template_id, position=1, header_label="AMOUNT",
                 value_type="distribution_node"):
    col = GlobalExportColumn(
        template_id=template_id,
        position=position,
        header_label=header_label,
        value_type=value_type,
        format_type="text",
    )
    db.add(col)
    db.flush()
    return col


# ── GET /api/export-templates ─────────────────────────────────────────────


def test_list_templates_empty(client):
    r = client.get("/api/export-templates")
    assert r.status_code == 200
    assert r.json() == []


def test_list_templates_returns_all(client, db):
    _seed_template(db, "T1")
    _seed_template(db, "T2")
    r = client.get("/api/export-templates")
    assert r.status_code == 200
    assert len(r.json()) == 2


# ── GET /api/export-templates/{id} ───────────────────────────────────────


def test_get_template_returns_404_for_missing(client):
    r = client.get("/api/export-templates/9999")
    assert r.status_code == 404


def test_get_template_returns_columns(client, db):
    t = _seed_template(db)
    _seed_column(db, t.id, 1, "DEAL_ID", "deal_meta")
    _seed_column(db, t.id, 2, "AMOUNT", "distribution_node")
    r = client.get(f"/api/export-templates/{t.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["template"]["id"] == t.id
    assert len(data["columns"]) == 2


# ── POST /api/export-templates/{id}/columns ───────────────────────────────


def test_create_column_requires_analytics(client, analyst_client, db):
    t = _seed_template(db)
    body = {"header_label": "COL", "value_type": "literal", "format_type": "text"}
    r = analyst_client.post(f"/api/export-templates/{t.id}/columns", json=body)
    assert r.status_code == 403


def test_create_column_as_analytics(client, db):
    t = _seed_template(db)
    body = {"header_label": "NEW_COL", "value_type": "literal", "literal_value": "X",
            "format_type": "text"}
    r = client.post(f"/api/export-templates/{t.id}/columns", json=body)
    assert r.status_code == 201
    assert r.json()["header_label"] == "NEW_COL"


def test_create_column_404_for_missing_template(client):
    body = {"header_label": "COL", "value_type": "literal", "format_type": "text"}
    r = client.post("/api/export-templates/9999/columns", json=body)
    assert r.status_code == 404


# ── PATCH /api/global-export-columns/{id} ────────────────────────────────


def test_update_column(client, db):
    t = _seed_template(db)
    col = _seed_column(db, t.id)
    r = client.patch(f"/api/global-export-columns/{col.id}", json={"header_label": "UPDATED"})
    assert r.status_code == 200
    assert r.json()["header_label"] == "UPDATED"


def test_update_column_404_for_missing(client):
    r = client.patch("/api/global-export-columns/9999", json={"header_label": "X"})
    assert r.status_code == 404


# ── DELETE /api/global-export-columns/{id} ───────────────────────────────


def test_delete_column(client, db):
    t = _seed_template(db)
    col = _seed_column(db, t.id)
    r = client.delete(f"/api/global-export-columns/{col.id}")
    assert r.status_code == 204
    r2 = client.get(f"/api/export-templates/{t.id}")
    assert r2.json()["columns"] == []


def test_delete_column_404_for_missing(client):
    r = client.delete("/api/global-export-columns/9999")
    assert r.status_code == 404


# ── POST reorder ──────────────────────────────────────────────────────────


def test_reorder_columns(client, db):
    t = _seed_template(db)
    c1 = _seed_column(db, t.id, 1, "A")
    c2 = _seed_column(db, t.id, 2, "B")
    r = client.post(
        f"/api/export-templates/{t.id}/columns/reorder",
        json={"ordered_column_ids": [c2.id, c1.id]},
    )
    assert r.status_code == 200
    labels = [c["header_label"] for c in r.json()]
    assert labels == ["B", "A"]


# ── Deal export config ────────────────────────────────────────────────────


def test_get_deal_config_empty(client, db, test_deal):
    t = _seed_template(db)
    r = client.get(f"/api/deals/{test_deal.id}/export-config/{t.id}")
    assert r.status_code == 200
    assert r.json()["rows"] == []


def test_save_and_get_deal_config(client, db, test_deal):
    from app.models.dag import DagVersion, DagNode

    t = _seed_template(db)
    col = _seed_column(db, t.id, 1, "AMOUNT")

    version = DagVersion(deal_id=test_deal.id, version_number=1, created_by="t", is_current=1)
    db.add(version)
    db.flush()
    node = DagNode(
        deal_id=test_deal.id, dag_version_id=version.id, key="dist1", name="D1",
        node_type="distribution",
    )
    db.add(node)
    db.flush()

    body = {
        "rows": [
            {
                "node_id": node.id,
                "row_order": 1,
                "identifier_group": None,
                "cells": [{"column_id": col.id, "value_source": "node", "source_ref": "dist1"}],
            }
        ]
    }
    r = client.put(f"/api/deals/{test_deal.id}/export-config/{t.id}", json=body)
    assert r.status_code == 200
    assert len(r.json()["rows"]) == 1
    assert r.json()["rows"][0]["cells"][0]["source_ref"] == "dist1"


# ── GET /deals/{deal_id}/export-preview/{template_id} ────────────────────


def test_preview_json_returns_columns_and_rows(client, db, test_deal):
    t = _seed_template(db)
    _seed_column(db, t.id, 1, "DEAL_ID", "deal_meta")
    _seed_column(db, t.id, 2, "AMOUNT", "distribution_node")
    r = client.get(f"/api/deals/{test_deal.id}/export-preview/{t.id}")
    assert r.status_code == 200
    data = r.json()
    assert "columns" in data
    assert "rows" in data
    assert len(data["columns"]) == 2


def test_preview_json_empty_template(client, db, test_deal):
    t = _seed_template(db)
    r = client.get(f"/api/deals/{test_deal.id}/export-preview/{t.id}")
    assert r.status_code == 200
    assert r.json()["columns"] == []


# ── GET /deals/{deal_id}/export-preview/{template_id}/xlsx ───────────────


def test_preview_xlsx_returns_binary(client, db, test_deal):
    t = _seed_template(db)
    _seed_column(db, t.id, 1, "AMOUNT")
    r = client.get(f"/api/deals/{test_deal.id}/export-preview/{t.id}/xlsx")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert r.content[:2] == b"PK"


def test_preview_xlsx_content_disposition(client, db, test_deal):
    t = _seed_template(db)
    r = client.get(f"/api/deals/{test_deal.id}/export-preview/{t.id}/xlsx")
    assert "attachment" in r.headers.get("content-disposition", "")
