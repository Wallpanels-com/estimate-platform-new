from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal
import uuid
from datetime import datetime
import re


def login_identifier(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.@+\-]{2,253}", value):
        raise ValueError("Use a login with letters, numbers, dots, underscores or hyphens.")
    return value


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str
    _login = field_validator("email")(login_identifier)


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
    agentation_enabled: bool = False
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
    email: str = Field(min_length=3, max_length=254)
    _login = field_validator("email")(login_identifier)
    name: str = Field(min_length=1, max_length=120)
    role: Literal["user"] = "user"


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_login(cls, value):
        return login_identifier(value) if value is not None else None

    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Literal["user"] | None = None
    is_active: bool | None = None


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    onboarding_completed: bool | None = None
