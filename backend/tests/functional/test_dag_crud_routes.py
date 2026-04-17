"""Functional tests for single-node/edge CRUD and DAG import endpoints."""


def _save_dag(client, deal_id, nodes=None, edges=None):
    nodes = nodes or [
        {"key": "in1", "name": "Input", "node_type": "input_value", "input_source": "tape"},
        {"key": "calc1", "name": "Calc", "node_type": "calculation", "formula": "in1 * 2"},
    ]
    edges = edges or [{"source_key": "in1", "target_key": "calc1"}]
    r = client.post(
        f"/api/deals/{deal_id}/dag",
        json={"nodes": nodes, "edges": edges},
    )
    assert r.status_code == 201
    return r.json()


# ── POST /deals/{deal_id}/dag/nodes ───────────────────────────────────────


def test_create_node_returns_201(client, test_deal):
    r = client.post(
        f"/api/deals/{test_deal.id}/dag/nodes",
        json={"key": "new_node", "name": "New", "node_type": "input_value", "input_source": "tape"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["key"] == "new_node"
    assert data["id"] is not None


def test_create_node_adds_to_existing_version(client, test_deal):
    _save_dag(client, test_deal.id)
    client.post(
        f"/api/deals/{test_deal.id}/dag/nodes",
        json={"key": "extra", "name": "Extra", "node_type": "input_value", "input_source": "tape"},
    )
    r = client.get(f"/api/deals/{test_deal.id}/dag")
    keys = {n["key"] for n in r.json()["nodes"]}
    assert "extra" in keys
    assert "in1" in keys


def test_create_node_auto_creates_version_if_none(client, test_deal):
    # No prior save
    r = client.post(
        f"/api/deals/{test_deal.id}/dag/nodes",
        json={"key": "only_node", "name": "Only", "node_type": "input_value", "input_source": "tape"},
    )
    assert r.status_code == 201


def test_create_node_formula_syncs_edges(client, test_deal):
    _save_dag(client, test_deal.id)
    r_dag = client.get(f"/api/deals/{test_deal.id}/dag")
    in1_id = next(n["id"] for n in r_dag.json()["nodes"] if n["key"] == "in1")

    r = client.post(
        f"/api/deals/{test_deal.id}/dag/nodes",
        json={"key": "calc2", "name": "Calc2", "node_type": "calculation", "formula": "in1 + 5"},
    )
    assert r.status_code == 201
    r_dag2 = client.get(f"/api/deals/{test_deal.id}/dag")
    calc2_id = next(n["id"] for n in r_dag2.json()["nodes"] if n["key"] == "calc2")
    edges = r_dag2.json()["edges"]
    assert any(e["source_node_id"] == in1_id and e["target_node_id"] == calc2_id for e in edges)


# ── PATCH /dag/nodes/{id} ─────────────────────────────────────────────────


def test_patch_node_updates_name(client, test_deal):
    _save_dag(client, test_deal.id)
    r_dag = client.get(f"/api/deals/{test_deal.id}/dag")
    node_id = r_dag.json()["nodes"][0]["id"]
    r = client.patch(f"/api/dag/nodes/{node_id}", json={"name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"


def test_patch_node_returns_404_for_missing(client):
    r = client.patch("/api/dag/nodes/99999", json={"name": "x"})
    assert r.status_code == 404


def test_patch_node_formula_changes_sync_edges(client, test_deal):
    _save_dag(client, test_deal.id)
    r_dag = client.get(f"/api/deals/{test_deal.id}/dag")
    calc_id = next(n["id"] for n in r_dag.json()["nodes"] if n["key"] == "calc1")
    in1_id = next(n["id"] for n in r_dag.json()["nodes"] if n["key"] == "in1")

    # Add a second input node then update calc1 formula to remove reference to in1
    client.post(
        f"/api/deals/{test_deal.id}/dag/nodes",
        json={"key": "in2", "name": "In2", "node_type": "input_value", "input_source": "tape"},
    )
    client.patch(f"/api/dag/nodes/{calc_id}", json={"formula": "in2 * 5"})

    r_dag2 = client.get(f"/api/deals/{test_deal.id}/dag")
    edges = r_dag2.json()["edges"]
    assert not any(e["source_node_id"] == in1_id and e["target_node_id"] == calc_id for e in edges)


# ── DELETE /dag/nodes/{id} ────────────────────────────────────────────────


def test_delete_node_removes_it(client, test_deal):
    _save_dag(client, test_deal.id)
    r_dag = client.get(f"/api/deals/{test_deal.id}/dag")
    node_id = r_dag.json()["nodes"][0]["id"]
    r = client.delete(f"/api/dag/nodes/{node_id}")
    assert r.status_code == 204
    r_dag2 = client.get(f"/api/deals/{test_deal.id}/dag")
    ids = {n["id"] for n in r_dag2.json()["nodes"]}
    assert node_id not in ids


def test_delete_node_returns_404_for_missing(client):
    r = client.delete("/api/dag/nodes/99999")
    assert r.status_code == 404


# ── POST /deals/{deal_id}/dag/edges ──────────────────────────────────────


def test_create_edge_between_existing_nodes(client, test_deal):
    _save_dag(client, test_deal.id)
    r_dag = client.get(f"/api/deals/{test_deal.id}/dag")
    nodes = r_dag.json()["nodes"]
    n1_id = nodes[0]["id"]
    n2_id = nodes[1]["id"]
    # Remove existing edge
    for e in r_dag.json()["edges"]:
        client.delete(f"/api/dag/edges/{e['id']}")

    r = client.post(
        f"/api/deals/{test_deal.id}/dag/edges",
        json={"source_node_id": n1_id, "target_node_id": n2_id},
    )
    assert r.status_code == 201
    assert r.json()["source_node_id"] == n1_id


def test_create_edge_deduplicates(client, test_deal):
    _save_dag(client, test_deal.id)
    r_dag = client.get(f"/api/deals/{test_deal.id}/dag")
    n1_id = r_dag.json()["nodes"][0]["id"]
    n2_id = r_dag.json()["nodes"][1]["id"]
    r1 = client.post(
        f"/api/deals/{test_deal.id}/dag/edges",
        json={"source_node_id": n1_id, "target_node_id": n2_id},
    )
    r2 = client.post(
        f"/api/deals/{test_deal.id}/dag/edges",
        json={"source_node_id": n1_id, "target_node_id": n2_id},
    )
    assert r1.json()["id"] == r2.json()["id"]


def test_create_edge_returns_error_for_missing_nodes(client, test_deal):
    # No DAG — no version → service returns None → error response
    r = client.post(
        f"/api/deals/{test_deal.id}/dag/edges",
        json={"source_node_id": 9999, "target_node_id": 9998},
    )
    assert r.status_code in (400, 404, 422)


# ── DELETE /dag/edges/{id} ────────────────────────────────────────────────


def test_delete_edge_removes_it(client, test_deal):
    _save_dag(client, test_deal.id)
    r_dag = client.get(f"/api/deals/{test_deal.id}/dag")
    edge_id = r_dag.json()["edges"][0]["id"]
    r = client.delete(f"/api/dag/edges/{edge_id}")
    assert r.status_code == 204
    r_dag2 = client.get(f"/api/deals/{test_deal.id}/dag")
    edge_ids = {e["id"] for e in r_dag2.json()["edges"]}
    assert edge_id not in edge_ids


def test_delete_edge_returns_404_for_missing(client):
    r = client.delete("/api/dag/edges/99999")
    assert r.status_code == 404


# ── POST /deals/{deal_id}/dag/import ─────────────────────────────────────


def test_dag_import_creates_version(client, test_deal):
    payload = {
        "version_number": 7,
        "nodes": [
            {"key": "n1", "name": "N1", "node_type": "input_value", "input_source": "tape"},
            {"key": "n2", "name": "N2", "node_type": "calculation", "formula": "n1 * 3"},
        ],
        "edges": [{"source_key": "n1", "target_key": "n2"}],
    }
    r = client.post(f"/api/deals/{test_deal.id}/dag/import", json=payload)
    assert r.status_code == 200
    assert r.json()["version_number"] == 1

    r2 = client.get(f"/api/deals/{test_deal.id}/dag")
    assert len(r2.json()["nodes"]) == 2


def test_dag_import_increments_over_existing(client, test_deal):
    _save_dag(client, test_deal.id)
    payload = {
        "nodes": [{"key": "x", "name": "X", "node_type": "input_value", "input_source": "tape"}],
        "edges": [],
    }
    r = client.post(f"/api/deals/{test_deal.id}/dag/import", json=payload)
    assert r.status_code == 200
    assert r.json()["version_number"] == 2
