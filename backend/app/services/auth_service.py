"""Authentication service — resolves Windows username to User record."""

from sqlalchemy.orm import Session
from app.models.user import User


class AuthService:
    """Looks up pre-registered users by Windows username."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user(self, username: str) -> User | None:
        """Return the user for *username*, or None if not registered."""
        return self.db.query(User).filter(User.username == username).first()
