"""DAG executor unit tests."""

from decimal import Decimal
from app.services.dag_executor import DagExecutor
from app.dag.service import DagService
from app.schemas.dag import DagNodeCreate, DagEdgeCreate
from app.models.processing import ProcessingRun, ExtractedValue
from app.models.servicer import Servicer
from app.models.deal import Deal


def _setup(db):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    deal = Deal(name="TEST", servicer_id=1, created_by="t")
    db.add(deal)
    db.flush()
    return deal


def test_execute_waterfall(db):
    deal = _setup(db)
    dag = DagService(db)
    dag.save(
        deal.id,
        [
            DagNodeCreate(key="total", name="Total", node_type="input_value", input_source="tape"),
            DagNodeCreate(
                key="fee_rate", name="Fee Rate", node_type="input_value", input_source="tape"
            ),
            DagNodeCreate(
                key="svc_fee", name="Svc Fee", node_type="calculation", formula="total * fee_rate"
            ),
            DagNodeCreate(
                key="net", name="Net", node_type="calculation", formula="total - svc_fee"
            ),
            DagNodeCreate(
                key="dist_fee",
                name="Fee Pmt",
                node_type="distribution",
                formula="svc_fee",
                export_field="SVC_FEE",
                payment_type="fee",
            ),
        ],
        [
            DagEdgeCreate(source_key="total", target_key="svc_fee"),
            DagEdgeCreate(source_key="fee_rate", target_key="svc_fee"),
            DagEdgeCreate(source_key="total", target_key="net"),
            DagEdgeCreate(source_key="svc_fee", target_key="net"),
            DagEdgeCreate(source_key="svc_fee", target_key="dist_fee"),
        ],
        "test",
    )

    run = ProcessingRun(deal_id=deal.id, report_period="2026-04", created_by="t")
    db.add(run)
    db.flush()
    db.add(
        ExtractedValue(
            run_id=run.id,
            variable_name="total",
            variable_id=1,
            sheet_name="S",
            cell_ref="A1",
            parsed_value=Decimal("4521338.42"),
            data_type="decimal",
        )
    )
    db.add(
        ExtractedValue(
            run_id=run.id,
            variable_name="fee_rate",
            variable_id=1,
            sheet_name="S",
            cell_ref="A2",
            parsed_value=Decimal("0.0025"),
            data_type="decimal",
        )
    )
    db.flush()

    result = DagExecutor(db).execute(run)
    assert len(result.errors) == 0
    step_map = {s.node_key: s for s in result.steps}
    assert step_map["svc_fee"].result == Decimal("4521338.42") * Decimal("0.0025")
    assert step_map["net"].result == Decimal("4521338.42") - step_map["svc_fee"].result
    assert result.distribution_total == step_map["svc_fee"].result


def test_execute_validation_pass(db):
    deal = _setup(db)
    dag = DagService(db)
    dag.save(
        deal.id,
        [
            DagNodeCreate(
                key="calc_oc",
                name="Calc OC",
                node_type="input_value",
                stream="validation",
                input_source="tape",
            ),
            DagNodeCreate(
                key="tape_oc",
                name="Tape OC",
                node_type="input_value",
                stream="validation",
                input_source="tape",
            ),
            DagNodeCreate(
                key="oc_check",
                name="OC Check",
                node_type="validation",
                stream="validation",
                formula="calc_oc",
                comparison_variable="tape_oc",
                tolerance=Decimal("0.01"),
                tolerance_type="absolute",
            ),
        ],
        [
            DagEdgeCreate(source_key="calc_oc", target_key="oc_check"),
            DagEdgeCreate(source_key="tape_oc", target_key="oc_check"),
        ],
        "test",
    )

    run = ProcessingRun(deal_id=deal.id, report_period="2026-04", created_by="t")
    db.add(run)
    db.flush()
    db.add(
        ExtractedValue(
            run_id=run.id,
            variable_name="calc_oc",
            variable_id=1,
            sheet_name="S",
            cell_ref="A1",
            parsed_value=Decimal("10685399.08"),
            data_type="decimal",
        )
    )
    db.add(
        ExtractedValue(
            run_id=run.id,
            variable_name="tape_oc",
            variable_id=1,
            sheet_name="S",
            cell_ref="A2",
            parsed_value=Decimal("10685399.08"),
            data_type="decimal",
        )
    )
    db.flush()

    result = DagExecutor(db).execute(run)
    assert result.validations_passed == 1
    assert result.validations_total == 1


def test_execute_validation_fail(db):
    deal = _setup(db)
    dag = DagService(db)
    dag.save(
        deal.id,
        [
            DagNodeCreate(
                key="calc_oc",
                name="Calc OC",
                node_type="input_value",
                stream="validation",
                input_source="tape",
            ),
            DagNodeCreate(
                key="tape_oc",
                name="Tape OC",
                node_type="input_value",
                stream="validation",
                input_source="tape",
            ),
            DagNodeCreate(
                key="oc_check",
                name="OC Check",
                node_type="validation",
                stream="validation",
                formula="calc_oc",
                comparison_variable="tape_oc",
                tolerance=Decimal("0.01"),
                tolerance_type="absolute",
            ),
        ],
        [
            DagEdgeCreate(source_key="calc_oc", target_key="oc_check"),
            DagEdgeCreate(source_key="tape_oc", target_key="oc_check"),
        ],
        "test",
    )

    run = ProcessingRun(deal_id=deal.id, report_period="2026-04", created_by="t")
    db.add(run)
    db.flush()
    db.add(
        ExtractedValue(
            run_id=run.id,
            variable_name="calc_oc",
            variable_id=1,
            sheet_name="S",
            cell_ref="A1",
            parsed_value=Decimal("8442100.00"),
            data_type="decimal",
        )
    )
    db.add(
        ExtractedValue(
            run_id=run.id,
            variable_name="tape_oc",
            variable_id=1,
            sheet_name="S",
            cell_ref="A2",
            parsed_value=Decimal("8891203.44"),
            data_type="decimal",
        )
    )
    db.flush()

    result = DagExecutor(db).execute(run)
    assert result.validations_passed == 0
    assert result.validations_total == 1


def test_lineage(db):
    deal = _setup(db)
    dag = DagService(db)
    dag.save(
        deal.id,
        [
            DagNodeCreate(key="a", name="A", node_type="input_value", input_source="tape"),
            DagNodeCreate(key="b", name="B", node_type="input_value", input_source="tape"),
            DagNodeCreate(key="c", name="C", node_type="calculation", formula="a + b"),
            DagNodeCreate(
                key="d",
                name="D",
                node_type="distribution",
                formula="c * 2",
                export_field="X",
                payment_type="test",
            ),
        ],
        [
            DagEdgeCreate(source_key="a", target_key="c"),
            DagEdgeCreate(source_key="b", target_key="c"),
            DagEdgeCreate(source_key="c", target_key="d"),
        ],
        "test",
    )

    run = ProcessingRun(deal_id=deal.id, report_period="2026-04", created_by="t")
    db.add(run)
    db.flush()
    db.add(
        ExtractedValue(
            run_id=run.id,
            variable_name="a",
            variable_id=1,
            sheet_name="S",
            cell_ref="A1",
            parsed_value=Decimal("10"),
            data_type="decimal",
        )
    )
    db.add(
        ExtractedValue(
            run_id=run.id,
            variable_name="b",
            variable_id=1,
            sheet_name="S",
            cell_ref="A2",
            parsed_value=Decimal("20"),
            data_type="decimal",
        )
    )
    db.flush()

    DagExecutor(db).execute(run)
    lineage = DagExecutor(db).get_lineage(run.id, "d")
    keys = [s.node_key for s in lineage]
    assert "a" in keys
    assert "b" in keys
    assert "c" in keys
    assert "d" in keys
    assert keys.index("a") < keys.index("c") < keys.index("d")
