"""Auth endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.user import User
from app.schemas.user import UserResponse, UserCreate

router = APIRouter()


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> User:
    user = User(username=body.username, display_name=body.display_name, role=body.role)
    db.add(user)
    db.flush()
    return user
