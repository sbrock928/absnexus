"""Clone service unit tests."""
from app.services.clone_service import CloneService
from app.dag.service import DagService
from app.schemas.dag import DagNodeCreate, DagEdgeCreate
from app.models.servicer import Servicer
from app.models.deal import Deal
from app.models.variable_mapping import VariableMapping
from app.models.variable import VariableDefinition
from app.models.tranche import DealTranche
from app.models.dag import DagNode, DagVersion


def _setup(db):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    deal = Deal(name="SOURCE", servicer_id=1, created_by="t")
    db.add(deal)
    db.flush()
    v = VariableDefinition(name="test_var", scope="system", data_type="decimal")
    db.add(v)
    db.flush()
    db.add(VariableMapping(deal_id=deal.id, variable_id=v.id, sheet_name="S1", column_letter="A", row_number=1))
    db.add(DealTranche(deal_id=deal.id, class_label="A", regulation_type="combined"))
    db.flush()
    DagService(db).save(deal.id, [
        DagNodeCreate(key="n1", name="N1", node_type="input_value", input_source="tape"),
        DagNodeCreate(key="n2", name="N2", node_type="calculation", formula="n1 * 2"),
    ], [DagEdgeCreate(source_key="n1", target_key="n2")], "test")
    return deal


def test_clone_copies_all(db):
    source = _setup(db)
    clone = CloneService(db).clone_deal(source.id, "CLONE", "tester")
    assert clone.name == "CLONE"
    assert clone.cloned_from_id == source.id
    assert clone.status == "draft"

    # Check mappings
    mappings = db.query(VariableMapping).filter(VariableMapping.deal_id == clone.id).all()
    assert len(mappings) == 1

    # Check tranches
    tranches = db.query(DealTranche).filter(DealTranche.deal_id == clone.id).all()
    assert len(tranches) == 1

    # Check DAG
    version = db.query(DagVersion).filter(DagVersion.deal_id == clone.id).first()
    assert version is not None
    assert version.version_number == 1
    nodes = db.query(DagNode).filter(DagNode.dag_version_id == version.id).all()
    assert len(nodes) == 2


def test_clone_without_dag(db):
    source = _setup(db)
    clone = CloneService(db).clone_deal(source.id, "CLONE2", "t", clone_dag=False)
    version = db.query(DagVersion).filter(DagVersion.deal_id == clone.id).first()
    assert version is None
