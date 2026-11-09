"""Portal identity is authoritative; estimates and HR keep their existing storage."""
import hashlib
import hmac
import json
import secrets
import time
import uuid
import httpx
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.user import User

IDENTITY_NAMESPACE = uuid.UUID('f130be91-c043-4ad6-b05e-22df4212b54d')
_client = httpx.AsyncClient(timeout=12, follow_redirects=False)


async def portal_request(action, data):
    if not settings.PORTAL_AUTH_ENABLED or len(settings.PORTAL_BRIDGE_SECRET) < 32:
        raise HTTPException(503, 'Unified sign-in is not configured.')
    path = '/integrations/estimate/' + action
    body = json.dumps(data, separators=(',', ':')).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(settings.PORTAL_BRIDGE_SECRET.encode(), stamp.encode() + b'.' + path.encode() + b'.' + body, hashlib.sha256).hexdigest()
    try:
        response = await _client.post(settings.PORTAL_BASE_URL.rstrip('/') + path, content=body,
                                      headers={'Content-Type': 'application/json', 'X-WP-Timestamp': stamp, 'X-WP-Signature': signature})
    except httpx.HTTPError:
        raise HTTPException(503, 'Account verification is temporarily unavailable. Please try again.')
    if response.status_code in (401, 403):
        raise HTTPException(401 if action == 'introspect' else response.status_code, 'Account unavailable or access removed. Sign in through WALLPANELS OS.')
    if response.status_code != 200:
        raise HTTPException(503, 'Account verification is temporarily unavailable. Please try again.')
    return response.json()


async def resolve_user(db, claims):
    # Only the authenticated portal owner maps to the existing Estimate owner.
    # Never auto-link by a matching email/name or grant another employee that ID.
    owner = claims.get('owner') is True
    owner_id = settings.ACCESS_MANAGER_USER_ID or settings.AGENTATION_USER_ID
    if owner and not owner_id:
        raise HTTPException(503, 'The Estimate owner identity is not configured.')
    user_id = owner_id if owner else uuid.uuid5(IDENTITY_NAMESPACE, settings.PORTAL_BASE_URL.rstrip('/') + ':' + claims['sub'])
    user = await db.get(User, user_id)
    if user is None:
        if owner:
            raise HTTPException(503, 'The Estimate owner identity is unavailable.')
        # An unreachable credential prevents local-login fallback for linked identities.
        await db.execute(insert(User).values(id=user_id, email=f'portal.{user_id}@wallpanels.invalid',
            name=claims['name'], role='user', is_active=True, onboarding_completed=True,
            password_hash=get_password_hash(secrets.token_urlsafe(32)), page_access=[], token_version=0
        ).on_conflict_do_nothing(index_elements=['id']))
        user = await db.get(User, user_id, populate_existing=True)
    if not user.is_active:
        raise HTTPException(401, 'This account is inactive.')
    if not owner and user.name != claims['name']:
        user.name = claims['name']
    user._portal_profile = claims
    db.info['actor'] = {'id': user.id, 'name': claims['name']}
    return user


async def sign_in(db, claims):
    user = await resolve_user(db, claims)
    return create_access_token({'sub': str(user.id), 'ver': user.token_version, 'portal_sub': claims['sub'],
                                'portal_version': claims['version'], 'portal_module': claims.get('module')})


async def verify_identity(db, token):
    if not token.get('portal_sub'):
        # Old standalone tokens cannot bypass the new authoritative account policy.
        raise HTTPException(401, 'Sign in with your WALLPANELS OS account.')
    claims = await portal_request('introspect', {'sub': token['portal_sub'], 'version': token.get('portal_version', ''),
                                               'module': token.get('portal_module')})
    user = await resolve_user(db, claims)
    if str(user.id) != token.get('sub') or token.get('ver') != user.token_version:
        raise HTTPException(401, 'Sign in again.')
    return user
