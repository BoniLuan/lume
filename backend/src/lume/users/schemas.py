from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    display_name: str
    base_currency: str
    locale: str
    timezone: str
    created_at: datetime


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def require_new_password(self) -> Self:
        if self.current_password == self.new_password:
            raise ValueError("new password must differ from the current password")
        return self
