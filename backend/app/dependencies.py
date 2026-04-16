"""FastAPI dependencies — auth, role enforcement, deal guards."""

import os
from typing import Any

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.deal import Deal
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.deal_service import DealService


def get_current_user(db: Session = Depends(get_db)) -> User:
    try:
        username = os.getlogin()
    except OSError:
        username = os.environ.get("USERNAME", os.environ.get("USER", "unknown"))

    user = AuthService(db).get_user(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User '{username}' is not registered.",
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
                detail=f"Role '{user.role}' not authorized.",
            )
        return user

    return _checker


def require_editable_deal(deal_id: int, db: Session = Depends(get_db)) -> Deal:
    """Block all writes when deal is archived."""
    deal = DealService(db).get(deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found.")
    if deal.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Deal is archived. Reactivate before editing.",
        )
    return deal


def require_processable_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Deal:
    """Analysts can only process active deals; analytics/admin can process any."""
    deal = DealService(db).get(deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal not found.")
    if user.role == "analyst" and deal.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analysts can only process active deals.",
        )
    return deal
