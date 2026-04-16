"""Functional tests for audit log routes."""

import json

from app.models.audit_log import AuditLog
from app.models.user import User


def _seed_audit(
    db, user_id, entity_type="deal", entity_id=1, action="create", changes=None, description=None
):
    entry = AuditLog(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changes=json.dumps(changes) if changes else None,
        description=description,
    )
    db.add(entry)
    db.flush()
    return entry


def _get_test_user(db):
    return db.query(User).filter(User.username == "testuser").first()


def test_list_empty(client):
    r = client.get("/api/audit/")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["page_size"] == 50
    assert body["has_more"] is False


def test_list_with_entries(client, db):
    user = _get_test_user(db)
    _seed_audit(db, user.id, description="Created deal X")

    r = client.get("/api/audit/")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["user_display_name"] == "Test User"
    assert item["entity_type"] == "deal"
    assert item["action"] == "create"
    assert item["description"] == "Created deal X"
    assert "created_at" in item


def test_filter_entity_type(client, db):
    user = _get_test_user(db)
    _seed_audit(db, user.id, entity_type="deal")
    _seed_audit(db, user.id, entity_type="variable")

    r = client.get("/api/audit/?entity_type=deal")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["entity_type"] == "deal"


def test_filter_action(client, db):
    user = _get_test_user(db)
    _seed_audit(db, user.id, action="create")
    _seed_audit(db, user.id, action="update")

    r = client.get("/api/audit/?action=update")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "update"


def test_entity_drill_in(client, db):
    user = _get_test_user(db)
    _seed_audit(db, user.id, entity_type="deal", entity_id=1)
    _seed_audit(db, user.id, entity_type="deal", entity_id=2)
    _seed_audit(db, user.id, entity_type="variable", entity_id=1)

    r = client.get("/api/audit/entity/deal/1")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["entity_type"] == "deal"
    assert body["items"][0]["entity_id"] == 1


def test_pagination_params(client, db):
    user = _get_test_user(db)
    for i in range(5):
        _seed_audit(db, user.id, entity_id=i)

    r = client.get("/api/audit/?page=1&page_size=2")
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["has_more"] is True

    r2 = client.get("/api/audit/?page=3&page_size=2")
    body2 = r2.json()
    assert len(body2["items"]) == 1
    assert body2["has_more"] is False


def test_changes_as_dict(client, db):
    user = _get_test_user(db)
    _seed_audit(db, user.id, changes={"name": {"old": "A", "new": "B"}})

    r = client.get("/api/audit/")
    body = r.json()
    assert body["items"][0]["changes"] == {"name": {"old": "A", "new": "B"}}


def test_null_changes(client, db):
    user = _get_test_user(db)
    _seed_audit(db, user.id, changes=None)

    r = client.get("/api/audit/")
    body = r.json()
    assert body["items"][0]["changes"] is None
