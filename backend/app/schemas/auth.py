from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: SecretStr = Field(min_length=1, max_length=128)


class UserProfile(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    expires_at: datetime
    user: UserProfile
