"""Page boundary tests: immutable owner, fail-closed APIs and Quick isolation."""
import sys, uuid, json
from pathlib import Path
from types import SimpleNamespace as O
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch
from starlette.requests import Request
from fastapi import HTTPException
from pydantic import ValidationError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/backend'))
from app.services import page_access as access
from app.schemas.auth import UserAccessUpdate
from app.api.v1 import users
from datetime import datetime, timezone


def request(path, method='GET', body=None):
    async def receive(): return {'type':'http.request','body':json.dumps(body or {}).encode()}
    return Request({'type':'http','method':method,'path':'/api/v1'+path,'headers':[],'query_string':b''}, receive)


def user(pages=None): return O(id=uuid.uuid4(), is_active=True, page_access=pages, email='employee', name='Employee')


class PageAccess(IsolatedAsyncioTestCase):
    async def test_default_access_and_owner_identity_do_not_depend_on_login_or_role(self):
        employee=user(); self.assertEqual(access.allowed_pages(employee), list(access.LEGACY_PAGES))
        employee.page_access=[]; self.assertFalse(access.allowed_pages(employee))
        with patch.object(access.settings,'ACCESS_MANAGER_USER_ID', employee.id):
            employee.email='renamed'; employee.name='Renamed'; employee.role='user'
            self.assertTrue(access.is_access_manager(employee))
            self.assertEqual(access.allowed_pages(employee), list(access.PAGES))
            self.assertFalse(access.is_access_manager(user()))
        employee.is_active=False
        with patch.object(access.settings,'ACCESS_MANAGER_USER_ID', employee.id): self.assertFalse(access.is_access_manager(employee))

    async def test_page_and_write_guards(self):
        cases=[
          (['estimates'],'/estimates','GET',True), (['quick_estimate'],'/estimates','GET',False),
          (['trash'],'/estimates/trash','GET',True), (['estimates'],'/estimates/trash','GET',False),
          (['users'],'/users','GET',True), (['estimates'],'/users','GET',False),
          (['users'],'/users','POST',False), (['users'],'/users/'+str(uuid.uuid4())+'/password','POST',False),
          (['users'],'/users/'+str(uuid.uuid4())+'/access','PUT',False),
          (['estimates'],'/pricing/schema','GET',True), (['quick_estimate'],'/pricing/quick-config','GET',True),
          (['estimates'],'/pricing/catalog/items/id/quote','POST',True),
          (['estimates'],'/pricing/config','PUT',False), (['estimates'],'/pricing/catalog/categories/quote','PUT',False), (['estimates'],'/pricing/catalog/items','POST',False),
          (['price_book'],'/pricing/config','PUT',True), (['price_book'],'/pricing/catalog/categories/id','DELETE',True),
          (['trash'],'/pricing/catalog','GET',False), ([], '/voice/extract','POST',False),
          ([], '/auth/me','GET',True), ([], '/auth/password','POST',True),
          (list(access.PAGES),'/audit','GET',False), (list(access.PAGES),'/operations/backups','POST',False),
          ([], '/future-hr-api','GET',False),
            (None, '/hr/vacancies','GET',False),
            (['hr'], '/hr/vacancies','GET',True),
            (['hr'], '/hr/candidates','PATCH',True),
        ]
        for pages,path,method,allowed in cases:
            with self.subTest(path=path,method=method,pages=pages):
                if allowed: await access.authorize_request(user(pages),O(),request(path,method))
                else:
                    with self.assertRaises(HTTPException) as error: await access.authorize_request(user(pages),O(),request(path,method))
                    self.assertEqual(error.exception.status_code,403)

    async def test_record_media_document_and_type_change_cannot_bypass_grants(self):
        ident=uuid.uuid4()
        for kind in ('pre','final','quick'):
            db=O(execute=AsyncMock(return_value=O(first=lambda:O(type=kind,deleted_at=None))))
            for path in (f'/estimates/{ident}', f'/pdf/{ident}/pre-estimate', f'/media/{ident}', f'/documents/{ident}'):
                with self.subTest(kind=kind,path=path):
                    if kind=='quick': await access.authorize_request(user(['quick_estimate']),db,request(path))
                    else:
                        with self.assertRaises(HTTPException): await access.authorize_request(user(['quick_estimate']),db,request(path))
                    await access.authorize_request(user(['estimates']),db,request(path))
        for method,suffix,body in [('PATCH','',{'type':'pre'}),('POST','/mode',{'mode':'final'})]:
            with self.assertRaises(HTTPException): await access.authorize_request(user(['quick_estimate']),db,request(f'/estimates/{ident}'+suffix,method,body))
        with self.assertRaises(HTTPException): await access.authorize_request(user(['quick_estimate']),db,request(f'/estimates/{str(ident).upper()}','PATCH',{'type':'pre'}))
        with self.assertRaises(HTTPException): await access.authorize_request(user(['quick_estimate']),O(),request('/estimates','POST',{'type':'pre'}))
        await access.authorize_request(user(['quick_estimate']),O(),request('/estimates','POST',{'type':'quick'}))

    async def test_owner_cannot_be_locked_out_and_stale_access_edits_are_rejected(self):
        owner=user([]); owner.updated_at=datetime.now(timezone.utc)
        db=O(execute=AsyncMock(return_value=O(scalar_one_or_none=lambda:owner)),commit=AsyncMock())
        with patch.object(access.settings,'ACCESS_MANAGER_USER_ID', owner.id):
            with self.assertRaises(HTTPException) as error: await users.update_user_access(owner.id,UserAccessUpdate(pages=[],expected_updated_at=owner.updated_at),db,owner)
            self.assertEqual(error.exception.status_code,409)
            with self.assertRaises(HTTPException) as error: await users.update_user_access(owner.id,UserAccessUpdate(pages=list(access.PAGES),expected_updated_at=datetime(2000,1,1,tzinfo=timezone.utc)),db,owner)
            self.assertEqual(error.exception.status_code,409)
        db.commit.assert_not_awaited()
        for pages in (['unknown'],['users','users']):
            with self.assertRaises(ValidationError): UserAccessUpdate(pages=pages,expected_updated_at=owner.updated_at)


class ForeignZoneBoundary(IsolatedAsyncioTestCase):
    async def test_foreign_zone_cannot_be_written_through_an_allowed_estimate(self):
        from app.api.v1 import estimates
        from app.schemas.estimate import LineItemCreate, LineItemUpdate
        from unittest.mock import Mock
        own=uuid.uuid4(); foreign=uuid.uuid4(); est=O(id=uuid.uuid4(), zones=[O(id=own)])
        item=O(zone_id=own)
        db=O(add=Mock(),execute=AsyncMock(return_value=O(scalar_one_or_none=lambda:item)),commit=AsyncMock())
        with patch.object(estimates,'load_estimate',new=AsyncMock(return_value=est)):
            with self.assertRaises(HTTPException) as error:
                await estimates.create_line_item(est.id,LineItemCreate(name='Scope',zone_id=foreign),db,O())
            self.assertEqual(error.exception.status_code,404)
            with self.assertRaises(HTTPException) as error:
                await estimates.update_line_item(est.id,uuid.uuid4(),LineItemUpdate(zone_id=foreign),db,O())
            self.assertEqual(error.exception.status_code,404)
        self.assertEqual(item.zone_id,own)
        db.add.assert_not_called();db.commit.assert_not_awaited()
