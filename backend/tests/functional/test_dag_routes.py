"""DAG route functional tests."""


def test_save_and_load_dag(client, db, test_deal):
    body = {
        "nodes": [
            {"key": "in1", "name": "Input", "node_type": "input_value", "input_source": "tape"},
            {"key": "calc1", "name": "Fee", "node_type": "calculation", "formula": "in1 * 0.0025"},
        ],
        "edges": [{"source_key": "in1", "target_key": "calc1"}],
        "description": "Test save",
    }
    r = client.post(f"/api/deals/{test_deal.id}/dag", json=body)
    assert r.status_code == 201
    assert r.json()["version_number"] == 1

    r2 = client.get(f"/api/deals/{test_deal.id}/dag")
    assert r2.status_code == 200
    data = r2.json()
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1


def test_version_history(client, db, test_deal):
    body = {"nodes": [{"key": "n1", "name": "N1", "node_type": "input_value", "input_source": "tape"}], "edges": []}
    client.post(f"/api/deals/{test_deal.id}/dag", json=body)
    client.post(f"/api/deals/{test_deal.id}/dag", json=body)
    r = client.get(f"/api/deals/{test_deal.id}/dag/versions")
    assert len(r.json()) == 2


def test_validate_dag(client, db, test_deal):
    body = {
        "nodes": [
            {"key": "in1", "name": "Input", "node_type": "input_value", "input_source": "tape"},
            {"key": "dist1", "name": "Dist", "node_type": "distribution", "formula": "in1", "export_field": "INT_PMT_A", "payment_type": "interest"},
        ],
        "edges": [{"source_key": "in1", "target_key": "dist1"}],
    }
    client.post(f"/api/deals/{test_deal.id}/dag", json=body)
    r = client.post(f"/api/deals/{test_deal.id}/dag/validate")
    assert r.json()["valid"] is True
