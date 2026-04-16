"""Unit tests for audit log DAO and query service."""

import json
from datetime import datetime, timedelta

from app.audit.dao import AuditLogDAO
from app.audit.service import AuditQueryService
from app.models.audit_log import AuditLog
from app.models.user import User


def _seed_user(db, username="testuser", display_name="Test User", role="analytics"):
    user = User(username=username, display_name=display_name, role=role)
    db.add(user)
    db.flush()
    return user


def _seed_entry(
    db,
    user_id,
    entity_type="deal",
    entity_id=1,
    action="create",
    changes=None,
    description=None,
    created_at=None,
):
    entry = AuditLog(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changes=json.dumps(changes) if changes else None,
        description=description,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(entry)
    db.flush()
    return entry


def test_list_all(db):
    user = _seed_user(db)
    _seed_entry(db, user.id, entity_type="deal", action="create")
    _seed_entry(db, user.id, entity_type="variable", action="update")
    _seed_entry(db, user.id, entity_type="deal", action="delete")

    rows, total = AuditLogDAO(db).list_filtered()
    assert total == 3
    assert len(rows) == 3


def test_filter_by_entity_type(db):
    user = _seed_user(db)
    _seed_entry(db, user.id, entity_type="deal")
    _seed_entry(db, user.id, entity_type="deal")
    _seed_entry(db, user.id, entity_type="variable")

    rows, total = AuditLogDAO(db).list_filtered(entity_type="deal")
    assert total == 2
    assert len(rows) == 2
    assert all(row[0].entity_type == "deal" for row in rows)


def test_filter_by_action(db):
    user = _seed_user(db)
    _seed_entry(db, user.id, action="create")
    _seed_entry(db, user.id, action="update")
    _seed_entry(db, user.id, action="update")

    rows, total = AuditLogDAO(db).list_filtered(action="update")
    assert total == 2
    assert all(row[0].action == "update" for row in rows)


def test_filter_by_user_id(db):
    user_a = _seed_user(db, username="alice", display_name="Alice")
    user_b = _seed_user(db, username="bob", display_name="Bob")
    _seed_entry(db, user_a.id)
    _seed_entry(db, user_a.id)
    _seed_entry(db, user_b.id)

    rows, total = AuditLogDAO(db).list_filtered(user_id=user_a.id)
    assert total == 2
    assert all(row[0].user_id == user_a.id for row in rows)


def test_filter_by_date_range(db):
    user = _seed_user(db)
    now = datetime.utcnow()
    _seed_entry(db, user.id, created_at=now - timedelta(days=5))
    _seed_entry(db, user.id, created_at=now - timedelta(days=2))
    _seed_entry(db, user.id, created_at=now)

    rows, total = AuditLogDAO(db).list_filtered(
        date_from=now - timedelta(days=3),
        date_to=now + timedelta(hours=1),
    )
    assert total == 2


def test_pagination(db):
    user = _seed_user(db)
    for i in range(10):
        _seed_entry(db, user.id, entity_id=i, created_at=datetime.utcnow() + timedelta(seconds=i))

    rows, total = AuditLogDAO(db).list_filtered(skip=0, limit=3)
    assert total == 10
    assert len(rows) == 3

    rows2, total2 = AuditLogDAO(db).list_filtered(skip=3, limit=3)
    assert total2 == 10
    assert len(rows2) == 3
    # No overlap
    ids_1 = {row[0].id for row in rows}
    ids_2 = {row[0].id for row in rows2}
    assert ids_1.isdisjoint(ids_2)


def test_ordering_newest_first(db):
    user = _seed_user(db)
    old = _seed_entry(db, user.id, created_at=datetime.utcnow() - timedelta(days=1))
    new = _seed_entry(db, user.id, created_at=datetime.utcnow())

    rows, _ = AuditLogDAO(db).list_filtered()
    assert rows[0][0].id == new.id
    assert rows[1][0].id == old.id


def test_combined_filters(db):
    user = _seed_user(db)
    _seed_entry(db, user.id, entity_type="deal", action="create")
    _seed_entry(db, user.id, entity_type="deal", action="update")
    _seed_entry(db, user.id, entity_type="variable", action="create")

    rows, total = AuditLogDAO(db).list_filtered(entity_type="deal", action="create")
    assert total == 1
    assert rows[0][0].entity_type == "deal"
    assert rows[0][0].action == "create"


def test_user_display_name_joined(db):
    user = _seed_user(db, display_name="Jane Chen")
    _seed_entry(db, user.id)

    rows, _ = AuditLogDAO(db).list_filtered()
    _, display_name = rows[0]
    assert display_name == "Jane Chen"


def test_service_changes_deserialized(db):
    user = _seed_user(db)
    _seed_entry(db, user.id, changes={"name": {"old": "A", "new": "B"}})

    result = AuditQueryService(db).list_entries()
    assert result.items[0].changes == {"name": {"old": "A", "new": "B"}}


def test_service_null_changes(db):
    user = _seed_user(db)
    _seed_entry(db, user.id, changes=None)

    result = AuditQueryService(db).list_entries()
    assert result.items[0].changes is None


def test_service_pagination_response(db):
    user = _seed_user(db)
    for i in range(5):
        _seed_entry(db, user.id, entity_id=i)

    result = AuditQueryService(db).list_entries(skip=0, limit=2)
    assert result.total == 5
    assert result.page == 1
    assert result.page_size == 2
    assert result.has_more is True
    assert len(result.items) == 2

    result2 = AuditQueryService(db).list_entries(skip=4, limit=2)
    assert result2.page == 3
    assert result2.has_more is False
    assert len(result2.items) == 1
