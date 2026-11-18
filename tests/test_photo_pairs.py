"""Shared ordered image pairs, private resources and uncropped geometry."""
from pathlib import Path
from types import SimpleNamespace as O
import sys, uuid, tempfile, itertools
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/backend'))
from app.services import photo_pair_trial as pair, page_access as access
from app.services.final_zone_layout import photos, photo_boxes
from app.services.proposal_brands import initial_layout
from app.api.v1 import estimates
from pydantic import ValidationError
from fastapi import HTTPException
from test_page_access import request, user
from test_final_zone_photos import fixture
import test_final_layout as fixtures
from test_final_layout import zone, estimate

class Pairs(TestCase):
    def test_validation_order_removal_and_shared_render(self):
        owner=user(); other=user(); est,z,_=fixture()
        with patch.object(access.settings,'ACCESS_MANAGER_USER_ID',owner.id):
            pair.select_pair(est,z,[3,1])
            self.assertEqual(pair.slots_for(est,z),[3,1])
            self.assertEqual(pair.presentation_view(est,owner).zones[0]._presentation_slots,[3,1])
            self.assertEqual(pair.presentation_view(est,other).zones[0]._presentation_slots,[3,1])
            self.assertFalse(hasattr(z,'_presentation_slots'))
            z.images=[O(slot=1)]
            self.assertEqual(pair.slots_for(est,z),[1])
        for slots in ([],[1,2,3],[0],[True],['1']):
            with self.assertRaises(ValidationError): pair.PhotoPairInput(slots=slots)
        for slots in ([1,1],[4]):
            with self.assertRaises(ValueError): pair.select_pair(est,z,slots)

    def test_shared_capability_respects_page_grants_and_portal_module(self):
        self.assertTrue(pair.available(user()))
        self.assertTrue(pair.available(user(['estimates'])))
        for pages in ([], ['hr'], ['quick_estimate']):
            self.assertFalse(pair.available(user(pages)))
        inactive=user(); inactive.is_active=False
        self.assertFalse(pair.available(inactive)); self.assertFalse(pair.available(None))
        portal=user(); portal._portal_profile={'owner':False,'module':'estimating','pages':['estimates']}
        self.assertTrue(pair.available(portal))
        portal._portal_profile['module']='hr'
        self.assertFalse(pair.available(portal))
        est,_,_=fixture(); est.type='pre'
        self.assertIs(pair.presentation_view(est,user()),est)

    def test_private_marker_survives_new_final(self):
        owner=user(); other=user()
        est=O(pdf_layout={pair.PRIVATE_KEY:str(owner.id)})
        self.assertEqual(initial_layout(est)[pair.PRIVATE_KEY],str(owner.id))
        with patch.object(access.settings,'ACCESS_MANAGER_USER_ID',owner.id):
            self.assertTrue(pair.can_read(est.pdf_layout,owner))
            self.assertFalse(pair.can_read(est.pdf_layout,other))
            owner.is_active=False
            self.assertFalse(pair.can_read(est.pdf_layout,owner))

    def test_all_orientation_pairs_fit_without_overlap_or_lost_rows(self):
        qa=fixtures.FinalLayout(); qa.setUp()
        try:
            imgs=qa.photos(3)
            for a,b in itertools.product(range(3),repeat=2):
                images=[O(**vars(imgs[a])),O(**vars(imgs[b]))]
                images[0].slot=1; images[1].slot=2
                z=zone('Living room TV wall',5,images=images); z._presentation_slots=[1,2]
                e=estimate([z])
                pdf=qa.check_geometry(e,f'pair-{a}-{b}.pdf')
                from app.services.final_zone_layout import paginate
                from app.services.final_pricing import quote
                self.assertEqual(len(paginate(z,1,quote(e))),1)
                text='\n'.join(p.extract_text() for p in pdf.pages)
                for n in range(5): self.assertEqual(text.count(f'Architectural scope {n+1}'),1)
                assets=photos(z)
                boxes=photo_boxes(assets,(674,90,728,702))
                for x,y,w,h in boxes:
                    self.assertGreaterEqual(x,674); self.assertGreaterEqual(y,90)
                    self.assertLessEqual(x+w,1402.01); self.assertLessEqual(y+h,792.01)
                self.assertTrue(boxes[0][0]+boxes[0][2]<=boxes[1][0] or boxes[1][1]+boxes[1][3]<=boxes[0][1])
        finally: qa.doCleanups()

class PrivateBoundary(IsolatedAsyncioTestCase):
    async def test_all_resource_routes_deny_even_unrestricted_employee(self):
        owner=user(); employee=user(); ident=uuid.uuid4()
        with patch.object(access.settings,'ACCESS_MANAGER_USER_ID',owner.id):
            for deleted in (None,'deleted'):
                row=O(type='final',deleted_at=deleted,pdf_layout={pair.PRIVATE_KEY:str(owner.id)})
                db=O(execute=AsyncMock(return_value=O(first=lambda:row)))
                paths=[(f'/estimates/{ident}','GET'),(f'/pdf/{ident}/final-estimate','GET'),(f'/media/{ident}','GET'),(f'/documents/{ident}','GET'),(f'/estimates/{ident}/restore','POST'),(f'/estimates/{ident}/permanent','DELETE')]
                for path,method in paths:
                    with self.assertRaises(HTTPException) as err:
                        await access.authorize_request(employee,db,request(path,method))
                    self.assertEqual(err.exception.status_code,404)
                    await access.authorize_request(owner,db,request(path,method))

    async def test_pair_endpoint_rejects_restricted_and_saves_employee(self):
        owner=user(); employee=user(); restricted=user(["hr"]); est,z,_=fixture(); db=O(commit=AsyncMock())
        with patch.object(access.settings,'ACCESS_MANAGER_USER_ID',owner.id), patch.object(estimates,'load_estimate',AsyncMock(return_value=est)):
            with self.assertRaises(HTTPException) as err:
                await estimates.set_zone_photo_pair(est.id,z.id,pair.PhotoPairInput(slots=[1,3]),db,restricted)
            self.assertEqual(err.exception.status_code,403); db.commit.assert_not_awaited()
            await estimates.set_zone_photo_pair(est.id,z.id,pair.PhotoPairInput(slots=[3,1]),db,employee)
            self.assertEqual(pair.slots_for(est,z),[3,1]); db.commit.assert_awaited_once()

    async def test_generic_patch_cannot_remove_or_forge_trial_markers(self):
        from app.schemas.estimate import EstimateUpdate
        owner=user(); est,z,_=fixture(); est.pdf_layout={pair.PRIVATE_KEY:str(owner.id),pair.KEY:{str(z.id):[3,1]}}
        db=O(flush=AsyncMock(),commit=AsyncMock())
        with patch.object(estimates,'load_estimate',AsyncMock(return_value=est)):
            await estimates.update_estimate(est.id,EstimateUpdate(pdf_layout={}),db,owner)
            self.assertEqual(est.pdf_layout[pair.PRIVATE_KEY],str(owner.id))
            self.assertEqual(est.pdf_layout[pair.KEY][str(z.id)],[3,1])
            est.pdf_layout=None
            await estimates.update_estimate(est.id,EstimateUpdate(pdf_layout={pair.PRIVATE_KEY:str(owner.id),pair.KEY:{str(z.id):[3,1]}}),db,owner)
            self.assertIsNone(est.pdf_layout)

    async def test_private_estimate_hidden_from_register_and_employee_cannot_create_one(self):
        from app.schemas.estimate import EstimateCreate
        owner=user(); employee=user()
        root=O(id=uuid.uuid4(),pdf_layout={pair.PRIVATE_KEY:str(owner.id)},branch_state={})
        db=O(execute=AsyncMock(return_value=O(scalars=lambda:O(all=lambda:[root]))))
        self.assertEqual(await estimates.estimate_register(db,user=employee),[])
        with patch.object(access.settings,'ACCESS_MANAGER_USER_ID',owner.id):
            with self.assertRaises(HTTPException) as err:
                await estimates.create_estimate(EstimateCreate(type='final',private_preview=True),db,employee)
            self.assertEqual(err.exception.status_code,403)
