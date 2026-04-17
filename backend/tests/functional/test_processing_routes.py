"""Processing route functional tests."""

import tempfile, openpyxl, os
from app.models.servicer import Servicer
from app.models.deal import Deal
from app.models.variable import VariableDefinition
from app.models.variable_mapping import VariableMapping
from app.dag.service import DagService
from app.schemas.dag import DagNodeCreate, DagEdgeCreate


def _setup_deal_with_dag(db):
    """Create a deal with mappings and a simple DAG."""
    s = db.query(Servicer).first()
    if not s:
        s = Servicer(name="WF", short_code="WF")
        db.add(s)
        db.flush()

    d = Deal(name="PROC-TEST", servicer_id=s.id, created_by="testuser")
    db.add(d)
    db.flush()

    v = VariableDefinition(name="amount", scope="system", data_type="decimal")
    db.add(v)
    db.flush()

    db.add(
        VariableMapping(
            deal_id=d.id, variable_id=v.id, sheet_name="Sheet1", column_letter="A", row_number=1
        )
    )
    db.flush()

    DagService(db).save(
        d.id,
        [
            DagNodeCreate(
                key="amount", name="Amount", node_type="input_value", input_source="tape"
            ),
            DagNodeCreate(
                key="pmt",
                name="Payment",
                node_type="distribution",
                formula="amount",
                export_field="PMT",
                payment_type="principal",
            ),
        ],
        [DagEdgeCreate(source_key="amount", target_key="pmt")],
        "testuser",
    )

    return d


def _make_tape(value):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = value
    path = tempfile.mktemp(suffix=".xlsx")
    wb.save(path)
    return path


def test_full_processing_flow(client, db):
    deal = _setup_deal_with_dag(db)

    # Step 1: Create run
    r = client.post(f"/api/deals/{deal.id}/runs", json={"report_period": "2026-04"})
    assert r.status_code == 201
    run_id = r.json()["id"]

    # Step 2: Upload tape
    path = _make_tape(1000000)
    with open(path, "rb") as f:
        r = client.post(
            f"/api/deals/{deal.id}/runs/{run_id}/upload", files={"file": ("tape.xlsx", f)}
        )
    os.unlink(path)
    assert r.status_code == 200

    # Step 3: Extract
    r = client.post(f"/api/deals/{deal.id}/runs/{run_id}/extract")
    assert r.status_code == 200
    assert r.json()["extracted"] == 1

    # Step 4: Execute
    r = client.post(f"/api/deals/{deal.id}/runs/{run_id}/execute")
    assert r.status_code == 200
    assert r.json()["status"] == "executed"
    assert float(r.json()["total_distribution"]) == 1000000

    # Step 5: Get trace
    r = client.get(f"/api/deals/{deal.id}/runs/{run_id}/trace")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_clone_deal(client, db):
    deal = _setup_deal_with_dag(db)
    r = client.post(f"/api/deals/{deal.id}/clone", json={"new_name": "CLONED"})
    assert r.status_code == 201
    assert r.json()["cloned_from_id"] == deal.id
