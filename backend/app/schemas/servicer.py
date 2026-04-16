"""Servicer schemas."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ServicerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    short_code: str
    created_at: datetime


class ServicerCreate(BaseModel):
    name: str
    short_code: str
