from fastapi import APIRouter, Depends, HTTPException, status, Request
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
from pydantic import Field
import time
from collections import deque

router = APIRouter(prefix="/auth", tags=["auth"])
_attempts = {}


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if settings.PORTAL_AUTH_ENABLED or not settings.ALLOW_SELF_REGISTRATION:
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
        page_access=[],  # Public sign-up never grants work pages without approval.
    )
    db.add(user)
    await db.flush()
    token = create_access_token({"sub": str(user.id), "ver": user.token_version})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db), request: Request = None):
    if settings.PORTAL_AUTH_ENABLED:
        now = time.monotonic()
        key = (request.client.host if request and request.client else '', data.email)
        attempts = _attempts.setdefault(key, deque(maxlen=10))
        if len(attempts) == 10 and now - attempts[0] < 300:
            raise HTTPException(429, 'Too many sign-in attempts. Try again in five minutes.')
        attempts.append(now)
        if len(_attempts) > 5000:
            for previous in list(_attempts):
                if now - _attempts[previous][-1] > 300:
                    _attempts.pop(previous, None)
        from app.services.portal_identity import portal_request, sign_in
        claims = await portal_request('authenticate', {'login': data.email, 'password': data.password})
        _attempts.pop(key, None)
        return TokenResponse(access_token=await sign_in(db, claims))
    result = await db.execute(select(User).where(User.email == str(data.email).lower()))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "ver": user.token_version})
    return TokenResponse(access_token=token)


class PortalCode(BaseModel):
    code: str = Field(min_length=32, max_length=100)


@router.post('/portal-exchange', response_model=TokenResponse)
async def portal_exchange(data: PortalCode, db: AsyncSession = Depends(get_db)):
    from app.services.portal_identity import portal_request, sign_in
    claims = await portal_request('exchange', {'code': data.code})
    return TokenResponse(access_token=await sign_in(db, claims))


def user_profile(user: User) -> UserOut:
    profile = UserOut.model_validate(user)
    from app.services.page_access import allowed_pages, is_access_manager
    profile.page_access = allowed_pages(user)
    profile.can_manage_access = is_access_manager(user)
    profile.agentation_enabled = bool(user.is_active and settings.AGENTATION_USER_ID and user.id == settings.AGENTATION_USER_ID)
    identity = getattr(user, '_portal_profile', None)
    if identity is not None:
        profile.email = identity['login']
        profile.name = identity['name']
        profile.portal_managed = True
        profile.agentation_enabled = profile.agentation_enabled and identity.get('module') is None
    return profile


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return user_profile(current_user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    data: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if getattr(current_user, "_portal_profile", None) is not None and data.name is not None:
        raise HTTPException(409, "Update your profile in WALLPANELS OS.")
    values = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in values.items():
        setattr(current_user, field, value)
    await db.flush()
    await db.commit()
    return user_profile(current_user)


@router.get("/settings")
async def auth_settings():
    return {"self_registration": settings.ALLOW_SELF_REGISTRATION,
            'portal_auth': settings.PORTAL_AUTH_ENABLED, 'portal_url': settings.PORTAL_BASE_URL,
            "ai_enabled": bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "local-not-configured")}


class ChangePassword(PasswordInput):
    current_password: str


@router.post("/password", status_code=204)
async def change_password(data: ChangePassword, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if getattr(user, '_portal_profile', None) is not None:
        raise HTTPException(409, 'Change your password in WALLPANELS OS. It applies to both platforms.')
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect.")
    user.password_hash = get_password_hash(data.password)
    user.token_version += 1
    await db.commit()
