from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal
import uuid
from datetime import datetime


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    role: str
    is_active: bool
    onboarding_completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PasswordInput(BaseModel):
    password: str = Field(min_length=12, max_length=72)

    @field_validator("password")
    @classmethod
    def bcrypt_limit(cls, password):
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes.")
        return password


class UserCreate(PasswordInput):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    role: Literal["user"] = "user"


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Literal["user"] | None = None
    is_active: bool | None = None


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    onboarding_completed: bool | None = None
