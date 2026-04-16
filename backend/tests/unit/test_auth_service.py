"""Auth service unit tests."""

from app.services.auth_service import AuthService
from app.models.user import User


def test_get_user_found(db):
    db.add(User(username="alice", display_name="Alice", role="analyst"))
    db.flush()
    assert AuthService(db).get_user("alice") is not None


def test_get_user_not_found(db):
    assert AuthService(db).get_user("nobody") is None
