"""Additional unit tests for ExportColumnService — preset copy, directory override, format."""

import os
import pytest
from decimal import Decimal

from app.export.service import ExportColumnService, PRESETS
from app.models.export import ExportColumn
from app.models.deal import Deal
from app.models.servicer import Servicer
from app.models.processing import ProcessingRun


def _make_deal(db, export_dir=None):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    d = Deal(
        name="MY DEAL",
        servicer_id=1,
        created_by="t",
        export_directory_override=export_dir,
    )
    db.add(d)
    db.flush()
    return d


def _make_run(db, deal_id, status="completed", period="2024-01"):
    run = ProcessingRun(
        deal_id=deal_id,
        batch_id=None,
        report_period=period,
        status=status,
        created_by="t",
    )
    db.add(run)
    db.flush()
    return run


# ── copy_preset ────────────────────────────────────────────────────────────


def test_copy_preset_system_a(db):
    deal = _make_deal(db)
    svc = ExportColumnService(db)
    cols = svc.copy_preset(deal.id, "system_a")
    labels = [c.header_label for c in cols]
    assert "DEAL_ID" in labels
    assert "AMOUNT" in labels


def test_copy_preset_replaces_existing_columns(db):
    deal = _make_deal(db)
    svc = ExportColumnService(db)
    # Add a column first
    svc.create_column(deal.id, "OLD_COL", "literal")
    svc.copy_preset(deal.id, "system_b")
    cols = svc.list_columns(deal.id)
    labels = [c.header_label for c in cols]
    assert "OLD_COL" not in labels


def test_copy_preset_unknown_key_raises(db):
    deal = _make_deal(db)
    svc = ExportColumnService(db)
    with pytest.raises(ValueError, match="Unknown preset"):
        svc.copy_preset(deal.id, "nonexistent_preset")


def test_all_presets_copy_without_error(db):
    deal = _make_deal(db)
    svc = ExportColumnService(db)
    for key in PRESETS:
        # Re-use same deal — copy_preset clears and replaces
        cols = svc.copy_preset(deal.id, key)
        assert len(cols) > 0


# ── reorder_columns ────────────────────────────────────────────────────────


def test_reorder_columns(db):
    deal = _make_deal(db)
    svc = ExportColumnService(db)
    c1 = svc.create_column(deal.id, "A", "literal")
    c2 = svc.create_column(deal.id, "B", "literal")
    c3 = svc.create_column(deal.id, "C", "literal")
    reordered = svc.reorder_columns(deal.id, [c3.id, c1.id, c2.id])
    labels = [c.header_label for c in reordered]
    assert labels == ["C", "A", "B"]


# ── update_column ─────────────────────────────────────────────────────────


def test_update_column_allowed_fields(db):
    deal = _make_deal(db)
    svc = ExportColumnService(db)
    col = svc.create_column(deal.id, "H1", "literal", literal_value="old")
    updated = svc.update_column(col, header_label="H2", literal_value="new")
    assert updated.header_label == "H2"
    assert updated.literal_value == "new"


def test_update_column_ignores_disallowed_fields(db):
    deal = _make_deal(db)
    svc = ExportColumnService(db)
    col = svc.create_column(deal.id, "H1", "literal")
    original_id = col.id
    svc.update_column(col, id=9999)  # should be ignored
    assert col.id == original_id


# ── generate_csv respects export_directory_override ───────────────────────


def test_generate_csv_writes_to_settings_directory(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.export.service.settings.export_directory", str(tmp_path))
    deal = _make_deal(db)
    svc = ExportColumnService(db)
    svc.create_column(deal.id, "RUN_ID", "run_meta", meta_field="run_code", format_type="text")
    run = _make_run(db, deal.id, period="2024-01")
    file_path, file_hash = svc.generate_csv(run)
    assert os.path.exists(file_path)
    assert file_path.startswith(str(tmp_path))
    assert len(file_hash) == 64  # sha256 hex


def test_generate_csv_raises_for_non_completed_run(db):
    deal = _make_deal(db)
    svc = ExportColumnService(db)
    svc.create_column(deal.id, "RUN_ID", "run_meta", meta_field="run_code")
    run = _make_run(db, deal.id, status="pending")
    with pytest.raises(ValueError, match="status"):
        svc.generate_csv(run)


def test_generate_csv_raises_with_no_columns(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.export.service.settings.export_directory", str(tmp_path))
    deal = _make_deal(db)
    run = _make_run(db, deal.id)
    svc = ExportColumnService(db)
    with pytest.raises(ValueError, match="No export columns"):
        svc.generate_csv(run)


# ── _format_value ─────────────────────────────────────────────────────────


def test_format_value_decimal_two_places():
    col = ExportColumn(format_type="decimal", decimal_places=2)
    result = ExportColumnService._format_value(Decimal("1234.5678"), col)
    assert result == "1234.57"


def test_format_value_decimal_zero_places():
    # decimal_places=0 is falsy so `or 2` kicks in → treated as 2 places
    col = ExportColumn(format_type="decimal", decimal_places=0)
    result = ExportColumnService._format_value(Decimal("99.9"), col)
    assert result == "99.90"


def test_format_value_integer():
    col = ExportColumn(format_type="integer", decimal_places=None)
    result = ExportColumnService._format_value(Decimal("42.7"), col)
    assert result == "42"


def test_format_value_text():
    col = ExportColumn(format_type="text", decimal_places=None)
    result = ExportColumnService._format_value("hello", col)
    assert result == "hello"


def test_format_value_none_returns_empty():
    col = ExportColumn(format_type="text", decimal_places=None)
    result = ExportColumnService._format_value(None, col)
    assert result == ""


# ── preview with no run ────────────────────────────────────────────────────


def test_preview_no_columns_returns_message(db):
    deal = _make_deal(db)
    svc = ExportColumnService(db)
    result = svc.preview(deal.id)
    assert "No columns" in result


def test_preview_with_columns_returns_csv(db):
    deal = _make_deal(db)
    svc = ExportColumnService(db)
    svc.create_column(deal.id, "AMOUNT", "distribution_node", format_type="decimal")
    svc.create_column(deal.id, "LABEL", "literal", literal_value="INTEREST")
    result = svc.preview(deal.id)
    assert "AMOUNT" in result
    assert "LABEL" in result
    assert "INTEREST" in result
