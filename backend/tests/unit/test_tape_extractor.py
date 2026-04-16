"""Tape extractor unit tests."""

from decimal import Decimal
from app.services.tape_extractor import TapeExtractor
from app.models.processing import ProcessingRun
from app.models.variable_mapping import VariableMapping
from app.models.variable import VariableDefinition
from app.models.servicer import Servicer
from app.models.deal import Deal
import tempfile, openpyxl, os


def _make_deal_with_mapping(db):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    deal = Deal(name="TEST", servicer_id=1, created_by="t")
    db.add(deal)
    db.flush()
    v = VariableDefinition(name="total_collections", scope="system", data_type="decimal")
    db.add(v)
    db.flush()
    db.add(
        VariableMapping(
            deal_id=deal.id, variable_id=v.id, sheet_name="Sheet1", column_letter="B", row_number=2
        )
    )
    db.flush()
    return deal


def _make_tape(value):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["B2"] = value
    path = tempfile.mktemp(suffix=".xlsx")
    wb.save(path)
    return path


def test_extract_happy_path(db):
    deal = _make_deal_with_mapping(db)
    path = _make_tape(4521338.42)
    run = ProcessingRun(deal_id=deal.id, report_period="2026-04", created_by="t")
    db.add(run)
    db.flush()
    results = TapeExtractor(db).extract_all(run, path)
    os.unlink(path)
    assert len(results) == 1
    assert results[0].parsed_value == Decimal("4521338.42")
    assert results[0].variable_name == "total_collections"


def test_extract_missing_cell(db):
    deal = _make_deal_with_mapping(db)
    path = _make_tape(None)
    run = ProcessingRun(deal_id=deal.id, report_period="2026-04", created_by="t")
    db.add(run)
    db.flush()
    results = TapeExtractor(db).extract_all(run, path)
    os.unlink(path)
    assert results[0].warning is not None
    assert "empty" in results[0].warning


def test_large_delta_warning(db):
    deal = _make_deal_with_mapping(db)
    # Create a prior run
    prior = ProcessingRun(
        deal_id=deal.id, report_period="2026-03", status="completed", created_by="t"
    )
    db.add(prior)
    db.flush()
    from app.models.processing import ExtractedValue

    db.add(
        ExtractedValue(
            run_id=prior.id,
            variable_name="total_collections",
            variable_id=1,
            sheet_name="Sheet1",
            cell_ref="B2",
            parsed_value=Decimal("1000"),
            data_type="decimal",
        )
    )
    db.flush()
    # Now extract with very different value
    path = _make_tape(5000)
    run = ProcessingRun(deal_id=deal.id, report_period="2026-04", created_by="t")
    db.add(run)
    db.flush()
    results = TapeExtractor(db).extract_all(run, path)
    os.unlink(path)
    assert results[0].warning is not None
    assert "400" in results[0].warning  # 400% change
