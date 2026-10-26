from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserOut
from app.api.deps import get_current_user
from app.core.config import settings
from app.schemas.auth import PasswordInput, ProfileUpdate
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if not settings.ALLOW_SELF_REGISTRATION:
        raise HTTPException(403, "Accounts are created by an existing team member.")
    if len(data.password) < 12 or len(data.password.encode("utf-8")) > 72:
        raise HTTPException(422, "Password must have at least 12 characters and at most 72 UTF-8 bytes.")
    result = await db.execute(select(User).where(User.email == str(data.email).lower()))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=str(data.email).lower(),
        name=data.name,
        password_hash=get_password_hash(data.password),
        role="user",
    )
    db.add(user)
    await db.flush()
    token = create_access_token({"sub": str(user.id), "ver": user.token_version})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == str(data.email).lower()))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "ver": user.token_version})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(
    data: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    values = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in values.items():
        setattr(current_user, field, value)
    await db.flush()
    await db.commit()
    return current_user


@router.get("/settings")
async def auth_settings():
    return {"self_registration": settings.ALLOW_SELF_REGISTRATION}


class ChangePassword(PasswordInput):
    current_password: str


@router.post("/password", status_code=204)
async def change_password(data: ChangePassword, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect.")
    user.password_hash = get_password_hash(data.password)
    user.token_version += 1
    await db.commit()
