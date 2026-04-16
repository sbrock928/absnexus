"""User management service."""

from sqlalchemy.orm import Session

from app.models.user import User
from app.users.dao import UserDAO

VALID_ROLES = {"admin", "analytics", "analyst"}


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dao = UserDAO(db)

    def list_all(self) -> list[User]:
        return self.dao.list_all()

    def get(self, user_id: int) -> User | None:
        return self.dao.get(user_id)

    def update(self, user: User, role: str | None, is_active: bool | None) -> User:
        updates: dict[str, object] = {}
        if role is not None:
            if role not in VALID_ROLES:
                raise ValueError(
                    f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_ROLES))}"
                )
            updates["role"] = role
        if is_active is not None:
            updates["is_active"] = is_active
        if updates:
            self.dao.update(user, **updates)
        return user
