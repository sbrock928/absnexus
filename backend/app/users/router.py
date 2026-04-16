"""Users management — HTTP routing layer."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.users.service import UserService

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> list[User]:
    return UserService(db).list_all()


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> User:
    user = UserService(db).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    try:
        return UserService(db).update(user, role=body.role, is_active=body.is_active)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
