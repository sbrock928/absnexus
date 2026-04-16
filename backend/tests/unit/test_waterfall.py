"""Unit tests for waterfall balance tracking."""
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.dag.service import DagService
from app.models.deal import Deal
from app.models.processing import ProcessingRun, ExtractedValue, ExecutionStep
from app.models.servicer import Servicer
from app.models.variable import VariableDefinition
from app.models.variable_mapping import VariableMapping
from app.processing.service import ProcessingService
from app.schemas.dag import DagNodeCreate, DagEdgeCreate


def _make_deal_with_waterfall(db: Session, starting_var="total_available_funds"):
    """Helper: create a servicer + deal with waterfall config."""
    s = db.query(Servicer).first()
    if not s:
        s = Servicer(name="WF", short_code="WF")
        db.add(s)
        db.flush()
    d = Deal(
        name="WF-TEST",
        servicer_id=s.id,
        created_by="testuser",
        waterfall_starting_var=starting_var,
        waterfall_ending_var="end_available_funds",
        waterfall_tolerance=Decimal("0.01"),
    )
    db.add(d)
    db.flush()
    return d


def _make_run(db: Session, deal_id: int, status: str = "executed"):
    run = ProcessingRun(
        deal_id=deal_id,
        report_period="2026-04",
        status=status,
        created_by="testuser",
    )
    db.add(run)
    db.flush()
    return run


def _add_extracted(db: Session, run_id: int, var_name: str, value: Decimal, var_id: int = 1):
    ev = ExtractedValue(
        run_id=run_id,
        variable_name=var_name,
        variable_id=var_id,
        sheet_name="Sheet1",
        cell_ref="A1",
        raw_value=str(value),
        parsed_value=value,
    )
    db.add(ev)
    db.flush()
    return ev


def _add_exec_step(
    db: Session, run_id: int, node_id: int,
    key: str, name: str, order: int, result: Decimal,
    node_type: str = "distribution",
):
    step = ExecutionStep(
        run_id=run_id,
        step_order=order,
        node_id=node_id,
        node_key=key,
        node_name=name,
        node_type=node_type,
        stream="distribution",
        result=result,
    )
    db.add(step)
    db.flush()
    return step


class TestWaterfallBasic:

    def test_waterfall_steps_and_balance(self, db):
        """Distributions subtract from starting balance correctly."""
        deal = _make_deal_with_waterfall(db)
        run = _make_run(db, deal.id)

        # Extracted starting value
        v = VariableDefinition(name="total_available_funds", scope="system", data_type="decimal")
        db.add(v)
        db.flush()
        _add_extracted(db, run.id, "total_available_funds", Decimal("10000"), v.id)

        # DAG with 2 distribution nodes
        dag_svc = DagService(db)
        dag_svc.save(deal.id, [
            DagNodeCreate(key="fee", name="Fee", node_type="distribution", formula="1000", waterfall_order=1),
            DagNodeCreate(key="prin", name="Principal", node_type="distribution", formula="9000", waterfall_order=2),
        ], [], "testuser")

        # Get node IDs from saved version
        loaded = dag_svc.load(deal.id)
        fee_node = [n for n in loaded["nodes"] if n.key == "fee"][0]
        prin_node = [n for n in loaded["nodes"] if n.key == "prin"][0]

        _add_exec_step(db, run.id, fee_node.id, "fee", "Fee", 1, Decimal("1000"))
        _add_exec_step(db, run.id, prin_node.id, "prin", "Principal", 2, Decimal("9000"))

        wf = ProcessingService(db).get_waterfall(run.id)

        assert Decimal(wf["starting_balance"]) == Decimal("10000")
        assert len(wf["steps"]) == 2
        assert wf["steps"][0]["node_key"] == "fee"
        assert Decimal(wf["steps"][0]["remaining_after"]) == Decimal("9000")
        assert wf["steps"][1]["node_key"] == "prin"
        assert Decimal(wf["steps"][1]["remaining_after"]) == Decimal("0")
        assert Decimal(wf["final_calculated_remainder"]) == Decimal("0")

    def test_waterfall_order_respected(self, db):
        """Nodes with explicit waterfall_order sort in that order (not execution order)."""
        deal = _make_deal_with_waterfall(db)
        run = _make_run(db, deal.id)

        v = VariableDefinition(name="total_available_funds", scope="system", data_type="decimal")
        db.add(v)
        db.flush()
        _add_extracted(db, run.id, "total_available_funds", Decimal("10000"), v.id)

        dag_svc = DagService(db)
        dag_svc.save(deal.id, [
            DagNodeCreate(key="c", name="C", node_type="distribution", formula="100", waterfall_order=3),
            DagNodeCreate(key="a", name="A", node_type="distribution", formula="200", waterfall_order=1),
            DagNodeCreate(key="b", name="B", node_type="distribution", formula="300", waterfall_order=2),
        ], [], "testuser")

        loaded = dag_svc.load(deal.id)
        node_map = {n.key: n for n in loaded["nodes"]}

        # Execution steps are in creation order (c=1, a=2, b=3) — opposite of waterfall_order
        _add_exec_step(db, run.id, node_map["c"].id, "c", "C", 1, Decimal("100"))
        _add_exec_step(db, run.id, node_map["a"].id, "a", "A", 2, Decimal("200"))
        _add_exec_step(db, run.id, node_map["b"].id, "b", "B", 3, Decimal("300"))

        wf = ProcessingService(db).get_waterfall(run.id)
        assert [s["node_key"] for s in wf["steps"]] == ["a", "b", "c"]

    def test_reconciled_pass(self, db):
        """reconciled=True when final remainder matches tape ending balance."""
        deal = _make_deal_with_waterfall(db)
        run = _make_run(db, deal.id)

        v1 = VariableDefinition(name="total_available_funds", scope="system", data_type="decimal")
        v2 = VariableDefinition(name="end_available_funds", scope="system", data_type="decimal")
        db.add(v1)
        db.add(v2)
        db.flush()

        _add_extracted(db, run.id, "total_available_funds", Decimal("10000"), v1.id)
        _add_extracted(db, run.id, "end_available_funds", Decimal("7000"), v2.id)

        dag_svc = DagService(db)
        dag_svc.save(deal.id, [
            DagNodeCreate(key="fee", name="Fee", node_type="distribution", formula="3000", waterfall_order=1),
        ], [], "testuser")

        loaded = dag_svc.load(deal.id)
        fee_node = loaded["nodes"][0]
        _add_exec_step(db, run.id, fee_node.id, "fee", "Fee", 1, Decimal("3000"))

        wf = ProcessingService(db).get_waterfall(run.id)
        assert wf["reconciled"] is True
        assert wf["has_tape_value"] is True
        assert Decimal(wf["difference"]) == Decimal("0")

    def test_reconciled_fail(self, db):
        """reconciled=False when final remainder differs by more than tolerance."""
        deal = _make_deal_with_waterfall(db)
        run = _make_run(db, deal.id)

        v1 = VariableDefinition(name="total_available_funds", scope="system", data_type="decimal")
        v2 = VariableDefinition(name="end_available_funds", scope="system", data_type="decimal")
        db.add(v1)
        db.add(v2)
        db.flush()

        _add_extracted(db, run.id, "total_available_funds", Decimal("10000"), v1.id)
        _add_extracted(db, run.id, "end_available_funds", Decimal("0"), v2.id)

        dag_svc = DagService(db)
        dag_svc.save(deal.id, [
            DagNodeCreate(key="fee", name="Fee", node_type="distribution", formula="5000", waterfall_order=1),
        ], [], "testuser")

        loaded = dag_svc.load(deal.id)
        fee_node = loaded["nodes"][0]
        _add_exec_step(db, run.id, fee_node.id, "fee", "Fee", 1, Decimal("5000"))

        wf = ProcessingService(db).get_waterfall(run.id)
        assert wf["reconciled"] is False
        assert Decimal(wf["difference"]) == Decimal("5000")

    def test_no_ending_var_graceful(self, db):
        """If ending var not mapped, has_tape_value=False and reconciled=None."""
        deal = _make_deal_with_waterfall(db)
        deal.waterfall_ending_var = "nonexistent_var"
        db.flush()

        run = _make_run(db, deal.id)

        v = VariableDefinition(name="total_available_funds", scope="system", data_type="decimal")
        db.add(v)
        db.flush()
        _add_extracted(db, run.id, "total_available_funds", Decimal("1000"), v.id)

        dag_svc = DagService(db)
        dag_svc.save(deal.id, [
            DagNodeCreate(key="a", name="A", node_type="distribution", formula="100", waterfall_order=1),
        ], [], "testuser")
        loaded = dag_svc.load(deal.id)
        _add_exec_step(db, run.id, loaded["nodes"][0].id, "a", "A", 1, Decimal("100"))

        wf = ProcessingService(db).get_waterfall(run.id)
        assert wf["has_tape_value"] is False
        assert wf["reconciled"] is None

    def test_pending_run_raises(self, db):
        """Waterfall on a pending run raises ValueError."""
        deal = _make_deal_with_waterfall(db)
        run = _make_run(db, deal.id, status="pending")
        with pytest.raises(ValueError, match="Waterfall requires a completed run"):
            ProcessingService(db).get_waterfall(run.id)
