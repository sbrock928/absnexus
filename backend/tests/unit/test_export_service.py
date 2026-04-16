"""Unit tests for export column service."""

import pytest
from decimal import Decimal

from app.export.service import ExportColumnService, PRESETS
from app.models.export import ExportColumn
from app.models.deal import Deal
from app.models.servicer import Servicer


@pytest.fixture()
def deal(db):
    s = Servicer(name="Test Servicer", short_code="TS")
    db.add(s)
    db.flush()
    d = Deal(name="AMORT 2024-1", servicer_id=s.id, product_type="ABS Auto", created_by="testuser")
    db.add(d)
    db.flush()
    return d


class TestColumnCRUD:
    def test_create_column_auto_position(self, db, deal):
        svc = ExportColumnService(db)
        col = svc.create_column(
            deal.id, header_label="AMOUNT", value_type="literal", literal_value="123"
        )
        assert col.id is not None
        assert col.position == 1
        assert col.header_label == "AMOUNT"

        col2 = svc.create_column(
            deal.id, header_label="RUN_ID", value_type="run_meta", meta_field="run_code"
        )
        assert col2.position == 2

    def test_list_columns_ordered(self, db, deal):
        svc = ExportColumnService(db)
        svc.create_column(deal.id, header_label="B", value_type="literal", literal_value="b")
        svc.create_column(deal.id, header_label="A", value_type="literal", literal_value="a")
        cols = svc.list_columns(deal.id)
        assert len(cols) == 2
        assert cols[0].header_label == "B"
        assert cols[1].header_label == "A"

    def test_update_column(self, db, deal):
        svc = ExportColumnService(db)
        col = svc.create_column(
            deal.id, header_label="OLD", value_type="literal", literal_value="x"
        )
        svc.update_column(col, header_label="NEW", literal_value="y")
        assert col.header_label == "NEW"
        assert col.literal_value == "y"

    def test_delete_column(self, db, deal):
        svc = ExportColumnService(db)
        col = svc.create_column(
            deal.id, header_label="DEL", value_type="literal", literal_value="x"
        )
        svc.delete_column(col)
        assert svc.list_columns(deal.id) == []


class TestReorder:
    def test_reorder_columns(self, db, deal):
        svc = ExportColumnService(db)
        c1 = svc.create_column(deal.id, header_label="A", value_type="literal", literal_value="a")
        c2 = svc.create_column(deal.id, header_label="B", value_type="literal", literal_value="b")
        c3 = svc.create_column(deal.id, header_label="C", value_type="literal", literal_value="c")

        result = svc.reorder_columns(deal.id, [c3.id, c1.id, c2.id])
        assert [c.header_label for c in result] == ["C", "A", "B"]


class TestCopyPreset:
    def test_copy_system_a(self, db, deal):
        svc = ExportColumnService(db)
        cols = svc.copy_preset(deal.id, "system_a")
        assert len(cols) == len(PRESETS["system_a"]["columns"])
        assert cols[0].header_label == "DEAL_ID"

    def test_copy_system_b(self, db, deal):
        svc = ExportColumnService(db)
        cols = svc.copy_preset(deal.id, "system_b")
        assert len(cols) == len(PRESETS["system_b"]["columns"])
        # Should have prorate columns
        prorate_cols = [c for c in cols if c.prorate_by]
        assert len(prorate_cols) == 2

    def test_copy_system_c(self, db, deal):
        svc = ExportColumnService(db)
        cols = svc.copy_preset(deal.id, "system_c")
        assert len(cols) == len(PRESETS["system_c"]["columns"])
        cusip_col = [c for c in cols if c.header_label == "CUSIP"]
        assert len(cusip_col) == 1

    def test_copy_replaces_existing(self, db, deal):
        svc = ExportColumnService(db)
        svc.create_column(deal.id, header_label="OLD", value_type="literal", literal_value="x")
        cols = svc.copy_preset(deal.id, "system_a")
        assert cols[0].header_label == "DEAL_ID"
        assert len(cols) == len(PRESETS["system_a"]["columns"])

    def test_unknown_preset_raises(self, db, deal):
        svc = ExportColumnService(db)
        with pytest.raises(ValueError, match="Unknown preset"):
            svc.copy_preset(deal.id, "invalid_preset")


class TestPreview:
    def test_preview_no_columns(self, db, deal):
        svc = ExportColumnService(db)
        result = svc.preview(deal.id)
        assert result == "No columns configured."

    def test_preview_with_columns(self, db, deal):
        svc = ExportColumnService(db)
        svc.create_column(
            deal.id, header_label="FIELD", value_type="literal", literal_value="hello"
        )
        svc.create_column(
            deal.id, header_label="AMT", value_type="distribution_node", format_type="decimal"
        )
        result = svc.preview(deal.id)
        lines = result.strip().split("\n")
        assert len(lines) == 3  # header + 2 sample rows
        assert "FIELD" in lines[0]
        assert "AMT" in lines[0]
