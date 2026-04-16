"""Functional tests for user management routes."""

from app.models.user import User


def _seed_user(db, username, display_name="User", role="analyst", is_active=True):
    u = User(username=username, display_name=display_name, role=role, is_active=is_active)
    db.add(u)
    db.flush()
    return u


# ---------------------------------------------------------------------------
# POST /api/auth/users — create (admin only)
# ---------------------------------------------------------------------------


def test_create_user_requires_admin(client):
    """analytics role should be denied."""
    r = client.post(
        "/api/auth/users", json={"username": "new", "display_name": "New", "role": "analyst"}
    )
    assert r.status_code == 403


def test_create_user_as_admin(admin_client):
    r = admin_client.post(
        "/api/auth/users",
        json={"username": "newuser", "display_name": "New User", "role": "analyst"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "newuser"
    assert body["role"] == "analyst"
    assert body["is_active"] is True


# ---------------------------------------------------------------------------
# GET /api/users/ — list (admin only)
# ---------------------------------------------------------------------------


def test_list_users_requires_admin(client):
    r = client.get("/api/users/")
    assert r.status_code == 403


def test_list_users(admin_client, db):
    _seed_user(db, "alice", "Alice")
    _seed_user(db, "bob", "Bob")

    r = admin_client.get("/api/users/")
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()]
    assert "alice" in usernames
    assert "bob" in usernames


def test_list_users_includes_admin_user(admin_client):
    """Admin fixture user should appear in the list."""
    r = admin_client.get("/api/users/")
    assert r.status_code == 200
    usernames = [u["username"] for u in r.json()]
    assert "admin" in usernames


# ---------------------------------------------------------------------------
# PATCH /api/users/{id} — update role / deactivate (admin only)
# ---------------------------------------------------------------------------


def test_update_user_requires_admin(client, db):
    u = _seed_user(db, "target")
    r = client.patch(f"/api/users/{u.id}", json={"role": "analytics"})
    assert r.status_code == 403


def test_change_role(admin_client, db):
    u = _seed_user(db, "rolechange", role="analyst")
    r = admin_client.patch(f"/api/users/{u.id}", json={"role": "analytics"})
    assert r.status_code == 200
    assert r.json()["role"] == "analytics"


def test_deactivate_user(admin_client, db):
    u = _seed_user(db, "deactivateme", is_active=True)
    r = admin_client.patch(f"/api/users/{u.id}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_reactivate_user(admin_client, db):
    u = _seed_user(db, "reactivateme", is_active=False)
    r = admin_client.patch(f"/api/users/{u.id}", json={"is_active": True})
    assert r.status_code == 200
    assert r.json()["is_active"] is True


def test_update_user_invalid_role(admin_client, db):
    u = _seed_user(db, "badrole")
    r = admin_client.patch(f"/api/users/{u.id}", json={"role": "superuser"})
    assert r.status_code == 400


def test_update_user_not_found(admin_client):
    r = admin_client.patch("/api/users/99999", json={"role": "analyst"})
    assert r.status_code == 404


def test_update_role_and_active_together(admin_client, db):
    u = _seed_user(db, "combo", role="analyst", is_active=True)
    r = admin_client.patch(f"/api/users/{u.id}", json={"role": "analytics", "is_active": False})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "analytics"
    assert body["is_active"] is False
