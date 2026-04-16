"""Servicer CRUD."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import require_role
from app.models.servicer import Servicer
from app.models.user import User
from app.schemas.servicer import ServicerResponse, ServicerCreate

router = APIRouter()


@router.get("/", response_model=list[ServicerResponse])
def list_servicers(db: Session = Depends(get_db)) -> list[Servicer]:
    return db.query(Servicer).order_by(Servicer.name).all()


@router.post("/", response_model=ServicerResponse, status_code=201)
def create_servicer(
    body: ServicerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
) -> Servicer:
    svc = Servicer(name=body.name, short_code=body.short_code)
    db.add(svc)
    db.flush()
    return svc
