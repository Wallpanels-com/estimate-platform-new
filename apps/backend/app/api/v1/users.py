"""Shared account lifecycle. Every active employee has the same User role."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.auth import UserOut, UserCreate, UserUpdate, PasswordInput, UserAccessUpdate, UserAccessOut

from app.services.page_access import require_manager, allowed_pages, is_access_manager, PAGES

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(User).order_by(User.name, User.email))).scalars().all()


@router.post("", response_model=UserOut, status_code=201)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    require_manager(actor)
    # Serialize account creation/role changes without locking client estimates.
    from sqlalchemy import text
    await db.execute(text("SELECT pg_advisory_xact_lock(18724301)"))
    email = str(data.email).lower()
    if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise HTTPException(409, "Email already registered.")
    user = User(email=email, name=data.name, role=data.role, page_access=[], password_hash=get_password_hash(data.password))
    db.add(user)
    await db.commit()
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, data: UserUpdate, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    require_manager(actor)
    from sqlalchemy import text
    await db.execute(text("SELECT pg_advisory_xact_lock(18724301)"))
    user = await db.get(User, user_id, populate_existing=True)
    if not user:
        raise HTTPException(404, "User not found.")
    values = data.model_dump(exclude_unset=True, exclude_none=True)
    if "email" in values and values["email"] != user.email:
        duplicate = (await db.execute(select(User).where(User.email == values["email"], User.id != user.id))).scalar_one_or_none()
        if duplicate:
            raise HTTPException(409, "This login is already in use.")
    if user.id == actor.id and values.get("is_active") is False:
        raise HTTPException(409, "You cannot disable your own account.")
    if any(key in values and values[key] != getattr(user, key) for key in ("email", "role", "is_active")):
        user.token_version += 1
    for key, value in values.items():
        setattr(user, key, value)
    await db.commit()
    return user


@router.post("/{user_id}/password", status_code=204)
async def reset_password(user_id: uuid.UUID, data: PasswordInput, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    require_manager(actor)
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    user.password_hash = get_password_hash(data.password)
    user.token_version += 1
    await db.commit()


@router.get("/{user_id}/access", response_model=UserAccessOut)
async def get_user_access(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    require_manager(actor)
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    return {"pages": allowed_pages(user), "updated_at": user.updated_at, "protected_owner": is_access_manager(user)}


@router.put("/{user_id}/access", response_model=UserAccessOut)
async def update_user_access(user_id: uuid.UUID, data: UserAccessUpdate, db: AsyncSession = Depends(get_db), actor: User = Depends(get_current_user)):
    require_manager(actor)
    user = (await db.execute(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found.")
    if user.updated_at != data.expected_updated_at:
        raise HTTPException(409, "This employee account changed. Reopen access settings and try again.")
    if is_access_manager(user) and set(data.pages) != set(PAGES):
        raise HTTPException(409, "The platform owner always retains access to all pages.")
    user.page_access = list(data.pages)
    from datetime import datetime, timezone
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"pages": allowed_pages(user), "updated_at": user.updated_at, "protected_owner": is_access_manager(user)}
