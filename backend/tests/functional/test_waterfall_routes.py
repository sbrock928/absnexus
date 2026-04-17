"""Functional tests for waterfall endpoint."""

import os
import tempfile

import openpyxl

from app.dag.service import DagService
from app.models.deal import Deal
from app.models.servicer import Servicer
from app.models.variable import VariableDefinition
from app.models.variable_mapping import VariableMapping
from app.schemas.dag import DagNodeCreate, DagEdgeCreate


def _make_tape(value=1000000, sheet="Sheet1", cell="A1"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws[cell] = value
    path = tempfile.mktemp(suffix=".xlsx")
    wb.save(path)
    return path


def _setup_waterfall_deal(db):
    """Create a deal with waterfall config, mapping, and DAG."""
    s = db.query(Servicer).first()
    if not s:
        s = Servicer(name="WF", short_code="WF")
        db.add(s)
        db.flush()

    d = Deal(
        name="WF-ROUTE-TEST",
        servicer_id=s.id,
        created_by="testuser",
        waterfall_starting_var="amount",
        waterfall_ending_var="end_amount",
        waterfall_tolerance="0.01",
    )
    db.add(d)
    db.flush()

    v = VariableDefinition(name="amount", scope="system", data_type="decimal")
    db.add(v)
    db.flush()

    db.add(
        VariableMapping(
            deal_id=d.id,
            variable_id=v.id,
            sheet_name="Sheet1",
            column_letter="A",
            row_number=1,
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
                key="fee",
                name="Fee Pmt",
                node_type="distribution",
                formula="amount * 0.01",
                waterfall_order=1,
                payment_type="FEE",
            ),
            DagNodeCreate(
                key="prin",
                name="Principal",
                node_type="distribution",
                formula="amount * 0.99",
                waterfall_order=2,
                payment_type="PRIN",
            ),
        ],
        [
            DagEdgeCreate(source_key="amount", target_key="fee"),
            DagEdgeCreate(source_key="amount", target_key="prin"),
        ],
        "testuser",
    )

    return d


def test_waterfall_endpoint(client, db):
    deal = _setup_waterfall_deal(db)

    # Create run + upload + extract + execute
    r = client.post(f"/api/deals/{deal.id}/runs", json={"report_period": "2026-04"})
    assert r.status_code == 201
    run_id = r.json()["id"]

    path = _make_tape(1000000)
    with open(path, "rb") as f:
        client.post(f"/api/deals/{deal.id}/runs/{run_id}/upload", files={"file": ("tape.xlsx", f)})
    os.unlink(path)

    r = client.post(f"/api/deals/{deal.id}/runs/{run_id}/extract")
    assert r.status_code == 200

    r = client.post(f"/api/deals/{deal.id}/runs/{run_id}/execute")
    assert r.status_code == 200

    # Get waterfall
    r = client.get(f"/api/deals/{deal.id}/runs/{run_id}/waterfall")
    assert r.status_code == 200

    wf = r.json()
    assert wf["starting_var"] == "amount"
    assert wf["step_count"] == 2
    assert wf["steps"][0]["node_key"] == "fee"
    assert wf["steps"][1]["node_key"] == "prin"
    # No end_amount mapped, so reconciled should be None
    assert wf["has_tape_value"] is False
    assert wf["reconciled"] is None


def test_waterfall_not_completed_fails(client, db):
    s = db.query(Servicer).first()
    if not s:
        s = Servicer(name="WF", short_code="WF")
        db.add(s)
        db.flush()
    d = Deal(name="D", servicer_id=s.id, created_by="testuser")
    db.add(d)
    db.flush()

    r = client.post(f"/api/deals/{d.id}/runs", json={"report_period": "2026-04"})
    run_id = r.json()["id"]

    r = client.get(f"/api/deals/{d.id}/runs/{run_id}/waterfall")
    assert r.status_code == 400


def test_waterfall_config_endpoint(client, db):
    s = db.query(Servicer).first()
    if not s:
        s = Servicer(name="WF", short_code="WF")
        db.add(s)
        db.flush()
    d = Deal(name="D", servicer_id=s.id, created_by="testuser")
    db.add(d)
    db.flush()

    r = client.patch(
        f"/api/deals/{d.id}/waterfall-config",
        json={
            "waterfall_starting_var": "custom_start",
            "waterfall_ending_var": "custom_end",
            "waterfall_tolerance": "0.50",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["starting_var"] == "custom_start"
    assert data["ending_var"] == "custom_end"
    assert data["tolerance"] == "0.50"


def test_node_patch_waterfall_order(client, db):
    """PATCH /deals/{id}/dag/nodes/{node_id} updates waterfall_order."""
    s = db.query(Servicer).first()
    if not s:
        s = Servicer(name="WF", short_code="WF")
        db.add(s)
        db.flush()
    d = Deal(name="D", servicer_id=s.id, created_by="testuser")
    db.add(d)
    db.flush()

    DagService(db).save(
        d.id,
        [
            DagNodeCreate(key="fee", name="Fee", node_type="distribution", formula="100"),
        ],
        [],
        "testuser",
    )

    loaded = DagService(db).load(d.id)
    node_id = loaded["nodes"][0].id

    r = client.patch(
        f"/api/deals/{d.id}/dag/nodes/{node_id}",
        json={
            "waterfall_order": 5,
        },
    )
    assert r.status_code == 200
    assert r.json()["waterfall_order"] == 5
