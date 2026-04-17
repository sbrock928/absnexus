"""Unit tests for DAG service single-node/edge CRUD and import."""

import json
import os
import tempfile

import pytest

from app.dag.service import DagService
from app.models.dag import DagEdge, DagNode, DagVersion
from app.models.deal import Deal
from app.models.servicer import Servicer
from app.schemas.dag import DagEdgeCreate, DagNodeCreate


def _make_deal(db):
    db.add(Servicer(name="WF", short_code="WF"))
    db.flush()
    d = Deal(name="TEST", servicer_id=1, created_by="t")
    db.add(d)
    db.flush()
    return d


def _saved_deal(db):
    """Deal with an existing v1 DAG."""
    deal = _make_deal(db)
    svc = DagService(db)
    svc.save(
        deal.id,
        [
            DagNodeCreate(key="in1", name="Input 1", node_type="input_value", input_source="tape"),
            DagNodeCreate(key="calc1", name="Calc 1", node_type="calculation", formula="in1 * 2"),
        ],
        [DagEdgeCreate(source_key="in1", target_key="calc1")],
        "user",
    )
    return deal


# ── create_node ────────────────────────────────────────────────────────────


def test_create_node_creates_version_if_none(db):
    deal = _make_deal(db)
    svc = DagService(db)
    node = svc.create_node(deal.id, {"key": "n1", "name": "N1", "node_type": "input_value"})
    assert node.id is not None
    version = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    assert version is not None


def test_create_node_uses_existing_version(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    version_before = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    svc.create_node(deal.id, {"key": "n_new", "name": "New", "node_type": "input_value"})
    versions = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).all()
    assert len(versions) == 1
    assert versions[0].id == version_before.id


def test_create_node_accepts_node_key_alias(db):
    deal = _make_deal(db)
    svc = DagService(db)
    node = svc.create_node(deal.id, {"node_key": "alias_key", "name": "N", "node_type": "input_value"})
    assert node.key == "alias_key"


def test_create_node_strips_disallowed_fields(db):
    deal = _make_deal(db)
    svc = DagService(db)
    # passing an arbitrary unknown field should not raise
    node = svc.create_node(
        deal.id,
        {"key": "safe", "name": "Safe", "node_type": "input_value", "bogus_field": "ignored"},
    )
    assert node.key == "safe"


def test_create_node_auto_syncs_edges_from_formula(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    # calc1 already exists in v1; create a new calc that references it
    version = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    new_node = svc.create_node(
        deal.id,
        {"key": "calc2", "name": "Calc2", "node_type": "calculation", "formula": "calc1 + 1"},
    )
    # Edge from calc1 → calc2 should have been created
    edges = db.query(DagEdge).filter(DagEdge.target_node_id == new_node.id).all()
    assert len(edges) == 1
    src = db.query(DagNode).filter(DagNode.id == edges[0].source_node_id).first()
    assert src.key == "calc1"


# ── update_node ────────────────────────────────────────────────────────────


def test_update_node_changes_field(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    version = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    node = db.query(DagNode).filter(DagNode.dag_version_id == version.id, DagNode.key == "in1").first()
    updated = svc.update_node(node.id, {"name": "Updated Name"})
    assert updated.name == "Updated Name"


def test_update_node_returns_none_for_missing(db):
    deal = _make_deal(db)
    svc = DagService(db)
    result = svc.update_node(99999, {"name": "x"})
    assert result is None


def test_update_node_syncs_edges_when_formula_changes(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    version = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    calc = db.query(DagNode).filter(DagNode.dag_version_id == version.id, DagNode.key == "calc1").first()

    # Create an additional node for the updated formula to reference
    new_input = svc.create_node(deal.id, {"key": "in2", "name": "In2", "node_type": "input_value"})

    # Update formula to reference in2 instead of in1
    svc.update_node(calc.id, {"formula": "in2 * 3"})

    edges_to_calc = db.query(DagEdge).filter(DagEdge.target_node_id == calc.id).all()
    source_ids = {e.source_node_id for e in edges_to_calc}
    assert new_input.id in source_ids


def test_update_node_accepts_comparison_var_alias(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    version = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    node = db.query(DagNode).filter(DagNode.dag_version_id == version.id, DagNode.key == "calc1").first()
    svc.update_node(node.id, {"comparison_var": "some_variable"})
    assert node.comparison_variable == "some_variable"


# ── delete_node ────────────────────────────────────────────────────────────


def test_delete_node_removes_node_and_edges(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    version = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    node = db.query(DagNode).filter(DagNode.dag_version_id == version.id, DagNode.key == "in1").first()
    node_id = node.id
    result = svc.delete_node(node_id)
    assert result is True
    assert db.query(DagNode).filter(DagNode.id == node_id).first() is None
    # Edges referencing the deleted node should also be gone
    edges = db.query(DagEdge).filter(
        (DagEdge.source_node_id == node_id) | (DagEdge.target_node_id == node_id)
    ).all()
    assert edges == []


def test_delete_node_returns_false_for_missing(db):
    deal = _make_deal(db)
    svc = DagService(db)
    assert svc.delete_node(99999) is False


# ── create_edge ────────────────────────────────────────────────────────────


def test_create_edge_inserts_edge(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    version = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    nodes = db.query(DagNode).filter(DagNode.dag_version_id == version.id).all()
    n1, n2 = nodes[0], nodes[1]
    # Remove existing edge first
    db.query(DagEdge).filter(DagEdge.dag_version_id == version.id).delete()
    db.flush()

    edge = svc.create_edge(deal.id, n1.id, n2.id)
    assert edge is not None
    assert edge.source_node_id == n1.id
    assert edge.target_node_id == n2.id


def test_create_edge_deduplicates(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    version = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    nodes = db.query(DagNode).filter(DagNode.dag_version_id == version.id).all()
    n1, n2 = nodes[0], nodes[1]
    edge1 = svc.create_edge(deal.id, n1.id, n2.id)
    edge2 = svc.create_edge(deal.id, n1.id, n2.id)
    assert edge1.id == edge2.id


def test_create_edge_returns_none_without_version(db):
    deal = _make_deal(db)
    svc = DagService(db)
    result = svc.create_edge(deal.id, 1, 2)
    assert result is None


# ── delete_edge ────────────────────────────────────────────────────────────


def test_delete_edge_removes_edge(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    version = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    edge = db.query(DagEdge).filter(DagEdge.dag_version_id == version.id).first()
    edge_id = edge.id
    result = svc.delete_edge(edge_id)
    assert result is True
    assert db.query(DagEdge).filter(DagEdge.id == edge_id).first() is None


def test_delete_edge_returns_false_for_missing(db):
    deal = _make_deal(db)
    svc = DagService(db)
    assert svc.delete_edge(99999) is False


# ── _sync_edges_from_formula ───────────────────────────────────────────────


def test_sync_edges_removes_stale_edges(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    version = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    calc = db.query(DagNode).filter(DagNode.dag_version_id == version.id, DagNode.key == "calc1").first()

    # Update formula to not reference in1 anymore → stale edge should be removed
    calc.formula = "100"
    db.flush()
    svc._sync_edges_from_formula(calc)

    edges_to_calc = db.query(DagEdge).filter(DagEdge.target_node_id == calc.id).all()
    assert edges_to_calc == []


def test_sync_edges_does_nothing_for_empty_formula(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    version = db.query(DagVersion).filter(DagVersion.deal_id == deal.id).first()
    node = db.query(DagNode).filter(DagNode.dag_version_id == version.id, DagNode.key == "in1").first()
    node.formula = None
    db.flush()
    # should not raise
    svc._sync_edges_from_formula(node)


# ── import_from_file ───────────────────────────────────────────────────────


def test_import_from_file_creates_version(db):
    deal = _make_deal(db)
    svc = DagService(db)
    payload = {
        "version_number": 1,
        "nodes": [
            {"key": "in1", "name": "Input", "node_type": "input_value", "input_source": "tape"},
            {"key": "calc1", "name": "Calc", "node_type": "calculation", "formula": "in1 * 2"},
        ],
        "edges": [{"source_key": "in1", "target_key": "calc1"}],
    }
    version = svc.import_from_file(deal.id, payload, "user")
    assert version.version_number == 1
    data = svc.load(deal.id)
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1


def test_import_from_file_increments_version(db):
    deal = _saved_deal(db)
    svc = DagService(db)
    payload = {
        "version_number": 99,
        "nodes": [{"key": "x", "name": "X", "node_type": "input_value", "input_source": "tape"}],
        "edges": [],
    }
    version = svc.import_from_file(deal.id, payload, "user")
    assert version.version_number == 2


def test_import_from_file_ignores_bad_edges(db):
    deal = _make_deal(db)
    svc = DagService(db)
    payload = {
        "nodes": [{"key": "n1", "name": "N1", "node_type": "input_value", "input_source": "tape"}],
        "edges": [{"source_key": "missing_key", "target_key": "n1"}],
    }
    version = svc.import_from_file(deal.id, payload, "user")
    data = svc.load(deal.id)
    # Edge references a missing node → no edge created
    assert len(data["edges"]) == 0


# ── _dump_version_file ─────────────────────────────────────────────────────


def test_dump_version_file_writes_json(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.dag.service.settings.dag_archive_directory", str(tmp_path))
    deal = _make_deal(db)
    svc = DagService(db)
    nodes = [DagNodeCreate(key="n1", name="N1", node_type="input_value", input_source="tape")]
    version = svc.save(deal.id, nodes, [], "user")
    archive_file = tmp_path / str(deal.id) / "v1.json"
    assert archive_file.exists()
    data = json.loads(archive_file.read_text())
    assert data["version_number"] == 1
    assert len(data["nodes"]) == 1


def test_dump_version_file_uses_deal_override(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.dag.service.settings.dag_archive_directory", "/nonexistent/default")
    override_dir = str(tmp_path / "override")
    db.add(Servicer(name="SVC", short_code="SC"))
    db.flush()
    deal = Deal(name="D", servicer_id=1, created_by="t", dag_archive_directory_override=override_dir)
    db.add(deal)
    db.flush()
    svc = DagService(db)
    nodes = [DagNodeCreate(key="n1", name="N1", node_type="input_value", input_source="tape")]
    svc.save(deal.id, nodes, [], "user")
    archive_file = tmp_path / "override" / str(deal.id) / "v1.json"
    assert archive_file.exists()


def test_dump_version_file_silently_skips_on_error(db, monkeypatch):
    """OSError during file write should not prevent the DB save from succeeding."""
    monkeypatch.setattr("app.dag.service.settings.dag_archive_directory", "/dev/null/impossible")
    deal = _make_deal(db)
    svc = DagService(db)
    nodes = [DagNodeCreate(key="n1", name="N1", node_type="input_value", input_source="tape")]
    version = svc.save(deal.id, nodes, [], "user")
    assert version.id is not None
