from pydantic import BaseModel, EmailStr
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
    onboarding_completed: bool
    created_at: datetime

    class Config:
        from_attributes = True