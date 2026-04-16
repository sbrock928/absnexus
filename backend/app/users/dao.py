"""User data access layer."""

from sqlalchemy.orm import Session

from app.models.user import User


class UserDAO:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[User]:
        return self.db.query(User).order_by(User.display_name).all()

    def get(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def update(self, user: User, **kwargs: object) -> User:
        for key, value in kwargs.items():
            setattr(user, key, value)
        self.db.flush()
        return user
