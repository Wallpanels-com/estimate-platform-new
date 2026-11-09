"""Owner-managed page grants; nullable grants preserve existing employee access."""
import re
import uuid
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import settings

LEGACY_PAGES = ('estimates', 'quick_estimate', 'price_book', 'users', 'trash')
PAGES = (*LEGACY_PAGES, 'hr')


def is_access_manager(user):
    identity = getattr(user, '_portal_profile', None)
    if identity is not None:
        return bool(identity.get('owner') and identity.get('module') is None)
    owner = settings.ACCESS_MANAGER_USER_ID or settings.AGENTATION_USER_ID
    return bool(owner and getattr(user, 'is_active', False) and user.id == owner)


def allowed_pages(user):
    identity = getattr(user, '_portal_profile', None)
    if identity is not None:
        return [p for p in PAGES if p in identity.get('pages', [])]
    if is_access_manager(user):
        return list(PAGES)
    configured = getattr(user, 'page_access', None)
    return list(LEGACY_PAGES) if configured is None else [p for p in PAGES if p in configured]


def require_manager(user):
    if not is_access_manager(user):
        raise HTTPException(403, 'Only the platform owner can manage employee accounts and access.')


def require_any(user, *pages):
    if not set(allowed_pages(user)).intersection(pages):
        raise HTTPException(403, 'You do not have access to this page. Contact Dmitry.')


async def request_fields(request):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(422, 'Expected an object request body.')
    return body


async def authorize_request(user, db, request):
    """One boundary for every authenticated API, including media and exports."""
    path = request.url.path.removeprefix('/api/v1').rstrip('/')
    method = request.method
    if path.startswith('/auth/'):
        return  # Login/profile/password-self remain available even with no grants.
    if path == '/hr' or path.startswith('/hr/'):
        require_any(user, 'hr')
        return
    if path.startswith('/users'):
        require_any(user, 'users')
        if method not in ('GET', 'HEAD'):
            require_manager(user)
            if getattr(user, '_portal_profile', None) is not None:
                raise HTTPException(409, 'Manage accounts, passwords and permissions in WALLPANELS OS.')
        return
    if path.startswith('/operations/') or path == '/audit':
        require_manager(user)
        return
    if path.startswith('/pricing'):
        read = method in ('GET', 'HEAD') or (method == 'POST' and (re.fullmatch(r'/pricing/calc/(wall|cabinet|mirror)', path) or re.fullmatch(r'/pricing/catalog/items/[^/]+/quote', path)))
        require_any(user, *('estimates', 'quick_estimate', 'price_book') if read else ('price_book',))
        return
    if path.startswith('/voice/'):
        require_any(user, 'estimates', 'quick_estimate')
        return
    if path == '/estimates/trash' or re.fullmatch(r'/estimates/[^/]+/(restore|permanent)', path):
        require_any(user, 'trash')
        return
    if path == '/estimates':
        if method == 'POST':
            body = await request_fields(request)
            require_any(user, 'quick_estimate' if body.get('type') == 'quick' else 'estimates')
        else:
            require_any(user, 'estimates')
        return
    match = re.match(r'/(?:estimates|pdf)/([^/]+)', path)
    media = re.fullmatch(r'/media/([^/]+)', path)
    document = re.fullmatch(r'/documents/([^/]+)', path)
    if match or media or document:
        # Default/unrestricted employees retain the existing fast path. Restricted
        # users cannot use a Quick grant to read a regular estimate via a known ID.
        if {'estimates', 'quick_estimate', 'trash'}.issubset(allowed_pages(user)):
            return
        from app.models.estimate import Estimate, EstimateImage
        from app.models.governance import DocumentVersion
        try:
            ident = uuid.UUID((match or media or document).group(1))
        except ValueError:
            raise HTTPException(404, 'Estimate not found')
        query = select(Estimate.type, Estimate.deleted_at).where(Estimate.id == ident)
        if media:
            query = select(Estimate.type, Estimate.deleted_at).join(EstimateImage, EstimateImage.estimate_id == Estimate.id).where(EstimateImage.id == ident)
        elif document:
            query = select(Estimate.type, Estimate.deleted_at).join(DocumentVersion, DocumentVersion.estimate_id == Estimate.id).where(DocumentVersion.id == ident)
        row = (await db.execute(query)).first()
        if not row:
            raise HTTPException(404, 'Estimate not found')
        require_any(user, *('trash',) if row.deleted_at else ('estimates', 'quick_estimate') if row.type == 'quick' else ('estimates',))
        if row.deleted_at and method not in ('GET', 'HEAD'):
            raise HTTPException(409, 'Restore this estimate before editing it.')
        if method == 'POST' and path.endswith('/mode'):
            require_any(user, 'estimates')
        if method == 'PATCH' and match and path.startswith('/estimates/') and len(path.split('/')) == 3:
            body = await request_fields(request)
            if body.get('type'):
                require_any(user, 'quick_estimate' if body['type'] == 'quick' else 'estimates')
        return
    # New APIs must explicitly declare how they map to the page registry.
    raise HTTPException(403, 'This operation is not available for your account.')
