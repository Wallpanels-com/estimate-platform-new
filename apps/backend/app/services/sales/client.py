"""Read-only, fixed-origin GHL client with no generic mutation interface.

The sole POST is GHL's documented opportunities.readonly search operation.
Its endpoint and body are fixed here; it cannot create/update an opportunity.
"""
import asyncio
import re
import httpx
from app.core.config import settings

READ_PATHS = re.compile(r'/(?:users/|opportunities/(?:search|pipelines)|conversations/search|conversations/[A-Za-z0-9_-]+/messages|contacts/[A-Za-z0-9_-]+(?:/notes|/tasks)?|locations/[A-Za-z0-9_-]+/customFields|phone-system/numbers/location/[A-Za-z0-9_-]+|voice-ai/(?:agents|dashboard/call-logs(?:/[A-Za-z0-9_-]+)?)|conversations/locations/[A-Za-z0-9_-]+/messages/[A-Za-z0-9_-]+/transcription|conversations/messages/[A-Za-z0-9_-]+/locations/[A-Za-z0-9_-]+/recording)')


class GhlError(Exception):
    def __init__(self, status=503):
        self.status = status
        super().__init__('GHL access denied: check read scopes.' if status in (401,403) else 'GHL limit reached; retry scheduled.' if status==429 else f'GHL temporarily unavailable (HTTP {status}).')


class GhlClient:
    def __init__(self, transport=None):
        self.client = httpx.AsyncClient(base_url='https://services.leadconnectorhq.com',
            headers={'Authorization': 'Bearer '+settings.SALES_GHL_TOKEN, 'Version':'2021-07-28'},
            timeout=httpx.Timeout(25,connect=8),follow_redirects=False,transport=transport)

    async def close(self):
        await self.client.aclose()

    async def search_changed_opportunities(self, since, until, cursor=None):
        if not settings.SALES_GHL_TOKEN:
            raise GhlError(401)
        body={'locationId':settings.SALES_GHL_LOCATION_ID,'limit':100,
            'filters':[{'field':'date_updated','operator':'range','value':{'gte':since,'lte':until}}],
            'sort':[{'field':'date_updated','direction':'asc'}]}
        if cursor is not None:body['searchAfter']=cursor
        await asyncio.sleep(.14)
        try:
            response=await self.client.post('/opportunities/search',headers={'Version':'v3'},json=body)
        except httpx.HTTPError:raise GhlError() from None
        if not response.is_success:raise GhlError(response.status_code)
        try:return response.json()
        except ValueError:raise GhlError(502) from None

    async def get(self, path, params=None, binary=False):
        if not READ_PATHS.fullmatch(path):
            raise ValueError('Only allowlisted CRM read endpoints are permitted.')
        if not settings.SALES_GHL_TOKEN:
            raise GhlError(401)
        await asyncio.sleep(.14)
        try:
            response = await self.client.get(path,params=params)
        except httpx.HTTPError:
            raise GhlError() from None
        if not response.is_success:
            raise GhlError(response.status_code)
        if binary:
            return response.content, response.headers.get('content-type','audio/mpeg')
        try:
            return response.json()
        except ValueError:
            raise GhlError(502) from None
