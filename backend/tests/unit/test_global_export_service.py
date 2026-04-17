"""Unit tests for GlobalExportService — preview_structured, preview_xlsx, _placeholder_rows."""

import pytest

from app.global_export.service import GlobalExportService
from app.models.global_export import GlobalExportTemplate, GlobalExportColumn, DealExportRow, DealExportCell
from app.models.servicer import Servicer
from app.models.deal import Deal
from app.models.dag import DagNode, DagVersion


def _make_template(db, name="Test Template"):
    t = GlobalExportTemplate(name=name, description="desc")
    db.add(t)
    db.flush()
    return t


def _add_column(db, template_id, position, header_label, value_type="distribution_node",
                meta_field=None, literal_value=None):
    col = GlobalExportColumn(
        template_id=template_id,
        position=position,
        header_label=header_label,
        value_type=value_type,
        meta_field=meta_field,
        literal_value=literal_value,
        format_type="text",
    )
    db.add(col)
    db.flush()
    return col


def _make_deal(db):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    d = Deal(name="TEST DEAL", servicer_id=1, created_by="t")
    db.add(d)
    db.flush()
    return d


def _make_node(db, deal_id, key="dist1"):
    version = DagVersion(deal_id=deal_id, version_number=1, created_by="t", is_current=1)
    db.add(version)
    db.flush()
    node = DagNode(
        deal_id=deal_id,
        dag_version_id=version.id,
        key=key,
        name="Distribution 1",
        node_type="distribution",
    )
    db.add(node)
    db.flush()
    return node


# ── preview_structured ─────────────────────────────────────────────────────


def test_preview_structured_returns_columns_and_rows(db):
    deal = _make_deal(db)
    template = _make_template(db)
    _add_column(db, template.id, 1, "DEAL_ID", value_type="deal_meta", meta_field="deal_id")
    _add_column(db, template.id, 2, "AMOUNT", value_type="distribution_node")

    svc = GlobalExportService(db)
    result = svc.preview_structured(deal.id, template.id)

    assert result["columns"] == ["DEAL_ID", "AMOUNT"]
    assert len(result["rows"]) >= 1


def test_preview_structured_with_no_deal_config_returns_placeholder_row(db):
    deal = _make_deal(db)
    template = _make_template(db)
    _add_column(db, template.id, 1, "PAYMENT_DATE", value_type="run_meta", meta_field="payment_date")

    svc = GlobalExportService(db)
    result = svc.preview_structured(deal.id, template.id)
    # One placeholder row when no DealExportRow configured
    assert len(result["rows"]) == 1
    assert result["rows"][0][0] == "<payment_date>"


def test_preview_structured_empty_template(db):
    deal = _make_deal(db)
    template = _make_template(db)
    svc = GlobalExportService(db)
    result = svc.preview_structured(deal.id, template.id)
    assert result["columns"] == []
    # No columns → placeholder row is an empty list
    assert result["rows"] == [[]]


def test_preview_structured_literal_column(db):
    deal = _make_deal(db)
    template = _make_template(db)
    _add_column(db, template.id, 1, "TYPE", value_type="literal", literal_value="INTEREST")

    svc = GlobalExportService(db)
    result = svc.preview_structured(deal.id, template.id)
    assert result["rows"][0][0] == "INTEREST"


# ── _placeholder_rows ──────────────────────────────────────────────────────


def test_placeholder_rows_with_deal_config(db):
    deal = _make_deal(db)
    template = _make_template(db)
    col1 = _add_column(db, template.id, 1, "NODE_AMT", value_type="distribution_node")
    col2 = _add_column(db, template.id, 2, "LITERAL", value_type="literal", literal_value="C")

    node = _make_node(db, deal.id)

    row = DealExportRow(deal_id=deal.id, template_id=template.id, node_id=node.id, row_order=1)
    db.add(row)
    db.flush()

    cell1 = DealExportCell(row_id=row.id, column_id=col1.id, value_source="node", source_ref="dist1")
    cell2 = DealExportCell(row_id=row.id, column_id=col2.id, value_source="literal", source_ref="C")
    db.add(cell1)
    db.add(cell2)
    db.flush()

    svc = GlobalExportService(db)
    cols = [col1, col2]
    rows = svc._placeholder_rows(deal.id, template.id, cols)

    assert len(rows) == 1
    assert rows[0][0] == "<dist1>"
    assert rows[0][1] == "C"


def test_placeholder_rows_missing_cell_uses_default_placeholder(db):
    deal = _make_deal(db)
    template = _make_template(db)
    col1 = _add_column(db, template.id, 1, "AMOUNT", value_type="distribution_node")
    col2 = _add_column(db, template.id, 2, "EXTRA", value_type="distribution_node")

    node = _make_node(db, deal.id)
    row = DealExportRow(deal_id=deal.id, template_id=template.id, node_id=node.id, row_order=1)
    db.add(row)
    db.flush()

    # Only provide cell for col1, not col2
    db.add(DealExportCell(row_id=row.id, column_id=col1.id, value_source="node", source_ref="dist1"))
    db.flush()

    svc = GlobalExportService(db)
    cols = [col1, col2]
    rows = svc._placeholder_rows(deal.id, template.id, cols)
    assert len(rows[0]) == 2
    # col2 has no cell, should get a default placeholder (not empty crash)
    assert rows[0][1] is not None


# ── preview_xlsx ───────────────────────────────────────────────────────────


def test_preview_xlsx_returns_bytes(db):
    deal = _make_deal(db)
    template = _make_template(db)
    _add_column(db, template.id, 1, "DEAL_ID", value_type="deal_meta", meta_field="deal_id")
    _add_column(db, template.id, 2, "AMOUNT", value_type="distribution_node")

    svc = GlobalExportService(db)
    result = svc.preview_xlsx(deal.id, template.id)
    # xlsx starts with PK (zip) magic bytes
    assert isinstance(result, bytes)
    assert result[:2] == b"PK"


def test_preview_xlsx_empty_template_returns_valid_workbook(db):
    deal = _make_deal(db)
    template = _make_template(db)
    svc = GlobalExportService(db)
    result = svc.preview_xlsx(deal.id, template.id)
    assert isinstance(result, bytes)
    assert result[:2] == b"PK"


# ── template and column CRUD via service ──────────────────────────────────


def test_list_templates_empty(db):
    svc = GlobalExportService(db)
    assert svc.list_templates() == []


def test_get_template_with_columns_raises_for_missing(db):
    svc = GlobalExportService(db)
    with pytest.raises(ValueError, match="not found"):
        svc.get_template_with_columns(9999)


def test_get_template_with_columns_returns_data(db):
    template = _make_template(db)
    _add_column(db, template.id, 1, "COL1")
    svc = GlobalExportService(db)
    result = svc.get_template_with_columns(template.id)
    assert result.template.id == template.id
    assert len(result.columns) == 1
    assert result.columns[0].header_label == "COL1"


# ── deal config round-trip ────────────────────────────────────────────────


def test_save_and_get_deal_config(db):
    deal = _make_deal(db)
    template = _make_template(db)
    col = _add_column(db, template.id, 1, "AMT", value_type="distribution_node")
    node = _make_node(db, deal.id)

    svc = GlobalExportService(db)
    rows_data = [
        {
            "node_id": node.id,
            "row_order": 1,
            "identifier_group": None,
            "cells": [{"column_id": col.id, "value_source": "node", "source_ref": "dist1"}],
        }
    ]
    saved = svc.save_deal_config(deal.id, template.id, rows_data)
    assert len(saved.rows) == 1
    assert saved.rows[0].node_id == node.id
    assert saved.rows[0].cells[0].source_ref == "dist1"

    # Idempotent re-save
    saved2 = svc.save_deal_config(deal.id, template.id, rows_data)
    assert len(saved2.rows) == 1
