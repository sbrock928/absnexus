"""User schemas."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    username: str
    display_name: str
    role: str = "analyst"


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
