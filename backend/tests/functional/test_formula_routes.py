"""Formula route functional tests."""


def test_validate_formula(client):
    r = client.post("/api/formulas/validate", json={
        "formula": "MIN(a, b) + c",
        "known_variables": ["a", "b", "c"],
    })
    assert r.status_code == 200
    assert r.json()["valid"] is True


def test_validate_formula_unknown(client):
    r = client.post("/api/formulas/validate", json={
        "formula": "a + unknown",
        "known_variables": ["a"],
    })
    assert r.json()["valid"] is False


def test_test_formula(client):
    r = client.post("/api/formulas/test", json={
        "formula": "total * rate",
        "context": {"total": "1000", "rate": "0.05"},
    })
    assert r.json()["result"] == "50.00"
