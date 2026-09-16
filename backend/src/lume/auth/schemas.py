from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from lume.users.schemas import UserResponse


class SessionCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    transport: Literal["cookie", "bearer"] = "cookie"
    device_label: str | None = Field(default=None, max_length=100)


class SessionResponse(BaseModel):
    session_id: str
    user: UserResponse
    transport: Literal["cookie", "bearer"]
    expires_at: datetime
    csrf_token: str | None = None
    token: str | None = None


class SessionListItem(BaseModel):
    id: str
    transport: str
    device_label: str | None
    created_at: datetime
    last_seen_at: datetime
    absolute_expires_at: datetime
    current: bool
