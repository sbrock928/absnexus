"""DAG service unit tests."""
from app.dag.service import DagService
from app.schemas.dag import DagNodeCreate, DagEdgeCreate
from app.models.servicer import Servicer
from app.models.deal import Deal


def _make_deal(db):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    d = Deal(name="TEST", servicer_id=1, created_by="t")
    db.add(d)
    db.flush()
    return d


def test_save_creates_version(db):
    deal = _make_deal(db)
    svc = DagService(db)
    nodes = [
        DagNodeCreate(key="input1", name="Input 1", node_type="input_value", input_source="tape"),
        DagNodeCreate(key="calc1", name="Calc 1", node_type="calculation", formula="input1 * 2"),
    ]
    edges = [DagEdgeCreate(source_key="input1", target_key="calc1")]
    v = svc.save(deal.id, nodes, edges, "testuser", "Initial")
    assert v.version_number == 1
    assert v.is_current == 1


def test_save_increments_version(db):
    deal = _make_deal(db)
    svc = DagService(db)
    nodes = [DagNodeCreate(key="n1", name="N1", node_type="input_value", input_source="tape")]
    svc.save(deal.id, nodes, [], "testuser", "v1")
    v2 = svc.save(deal.id, nodes, [], "testuser", "v2")
    assert v2.version_number == 2


def test_revert_creates_new_version(db):
    deal = _make_deal(db)
    svc = DagService(db)
    nodes = [DagNodeCreate(key="n1", name="N1", node_type="input_value", input_source="tape")]
    v1 = svc.save(deal.id, nodes, [], "testuser", "v1")
    svc.save(deal.id, [DagNodeCreate(key="n2", name="N2", node_type="input_value", input_source="tape")], [], "testuser", "v2")
    v3 = svc.revert(deal.id, v1.id, "testuser")
    assert v3.version_number == 3

    data = svc.load(deal.id)
    assert len(data["nodes"]) == 1
    assert data["nodes"][0].key == "n1"


def test_stream_validation(db):
    deal = _make_deal(db)
    svc = DagService(db)
    nodes = [
        DagNodeCreate(key="dist_in", name="DI", node_type="input_value", stream="distribution", input_source="tape"),
        DagNodeCreate(key="val_calc", name="VC", node_type="validation", stream="validation", formula="dist_in * 1", comparison_variable="x"),
    ]
    edges = [DagEdgeCreate(source_key="dist_in", target_key="val_calc")]
    svc.save(deal.id, nodes, edges, "testuser")
    errors = svc.validate_dag(deal.id)
    assert any("Cross-stream" in e for e in errors)


def test_deactivate_node(db):
    deal = _make_deal(db)
    svc = DagService(db)
    nodes = [DagNodeCreate(key="n1", name="N1", node_type="input_value", input_source="tape")]
    svc.save(deal.id, nodes, [], "testuser")
    data = svc.load(deal.id)
    node_id = data["nodes"][0].id
    svc.deactivate_node(node_id)
    data2 = svc.load(deal.id)
    assert data2["nodes"][0].is_active == 0
