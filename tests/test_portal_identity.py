import sys, uuid
from pathlib import Path
from types import SimpleNamespace as O
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/backend'))
from app.services import portal_identity as portal
from app.services import page_access as access
from app.api.v1.auth import user_profile


class PortalIdentity(IsolatedAsyncioTestCase):
    async def test_owner_identity_is_explicit_and_scope_never_grants_hr_in_estimate_embed(self):
        ident=uuid.uuid4()
        person=O(id=ident,is_active=True,token_version=0)
        claims={'sub':'32','owner':True,'module':'estimating','pages':['estimates','quick_estimate','price_book','trash'],'name':'Owner','login':'dmitriy'}
        db=O(get=AsyncMock(return_value=person),info={})
        with patch.object(portal.settings,'ACCESS_MANAGER_USER_ID',ident):
            linked=await portal.resolve_user(db,claims)
            db.get.assert_awaited_once_with(portal.User,ident)
            self.assertEqual(access.allowed_pages(linked),claims['pages'])
            self.assertFalse(access.is_access_manager(linked))
            with self.assertRaises(HTTPException): access.require_any(linked,'hr')
        claims['module']=None;claims['pages'].extend(['hr','users'])
        self.assertTrue(access.is_access_manager(person))

    async def test_employee_never_links_by_email_and_lost_local_sessions_cannot_bypass_portal(self):
        person=O(id=uuid.uuid4(),is_active=True,token_version=0,name='Employee')
        claims={'sub':'55','owner':False,'module':'hr','pages':['hr'],'name':'Employee','login':'same-login-as-legacy'}
        db=O(get=AsyncMock(return_value=person),info={})
        await portal.resolve_user(db,claims)
        expected=uuid.uuid5(portal.IDENTITY_NAMESPACE,portal.settings.PORTAL_BASE_URL.rstrip('/')+':55')
        db.get.assert_awaited_once_with(portal.User,expected)
        self.assertEqual(access.allowed_pages(person),['hr'])
        with self.assertRaises(HTTPException): await portal.verify_identity(db,{'sub':str(person.id),'ver':0})

    async def test_current_access_is_verified_every_time_and_outages_fail_closed(self):
        ident=uuid.uuid4()
        person=O(id=ident,is_active=True,token_version=2,name='Employee')
        claims={'sub':'55','owner':False,'module':'hr','pages':['hr'],'name':'Employee','login':'employee'}
        db=O(get=AsyncMock(return_value=person),info={})
        token={'sub':str(ident),'ver':2,'portal_sub':'55','portal_version':'current','portal_module':'hr'}
        with patch.object(portal,'portal_request',AsyncMock(return_value=claims)) as check:
            await portal.verify_identity(db,token);await portal.verify_identity(db,token)
            self.assertEqual(check.await_count,2)
            self.assertEqual(check.call_args.args[1],{'sub':'55','version':'current','module':'hr'})
        with patch.object(portal,'portal_request',AsyncMock(side_effect=HTTPException(401,'archived'))):
            with self.assertRaises(HTTPException):await portal.verify_identity(db,token)
