"""FastAPI dependencies — auth, role enforcement."""
import os
from typing import Any

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import AuthService


def get_current_user(db: Session = Depends(get_db)) -> User:
    try:
        username = os.getlogin()
    except OSError:
        username = os.environ.get("USERNAME", os.environ.get("USER", "unknown"))

    user = AuthService(db).get_user(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User \'{username}\' is not registered.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )
    return user


def require_role(*allowed_roles: str) -> Any:
    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role \'{user.role}\' not authorized.",
            )
        return user
    return _checker
