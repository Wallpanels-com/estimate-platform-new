"""Shared account lifecycle. Every active employee has the same User role."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.auth import UserOut, UserCreate, UserUpdate, PasswordInput

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(User).order_by(User.name, User.email))).scalars().all()


@router.post("", response_model=UserOut, status_code=201)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Serialize account creation/role changes without locking client estimates.
    from sqlalchemy import text
    await db.execute(text("SELECT pg_advisory_xact_lock(18724301)"))
    email = str(data.email).lower()
    if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise HTTPException(409, "Email already registered.")
    user = User(email=email, name=data.name, role=data.role, password_hash=get_password_hash(data.password))
    db.add(user)
    await db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, data: UserUpdate, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    from sqlalchemy import text
    await db.execute(text("SELECT pg_advisory_xact_lock(18724301)"))
    user = await db.get(User, user_id, populate_existing=True)
    if not user:
        raise HTTPException(404, "User not found.")
    values = data.model_dump(exclude_unset=True, exclude_none=True)
    if user.id == actor.id and values.get("is_active") is False:
        raise HTTPException(409, "You cannot disable your own account.")
    if any(key in values and values[key] != getattr(user, key) for key in ("role", "is_active")):
        user.token_version += 1
    for key, value in values.items():
        setattr(user, key, value)
    await db.commit()
    return user


@router.post("/{user_id}/password", status_code=204)
async def reset_password(user_id: uuid.UUID, data: PasswordInput, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    user.password_hash = get_password_hash(data.password)
    user.token_version += 1
    await db.commit()
