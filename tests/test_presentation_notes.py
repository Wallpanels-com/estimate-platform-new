"""Owner-only notes: persistence, branch inheritance and bounded PDF text."""
import asyncio
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as O
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import patch, AsyncMock
import sys, tempfile, uuid
ROOT=Path(__file__).resolve().parents[1]

sys.path[:0]=[str(ROOT/'apps/backend'),str(ROOT/'tests')]
from pydantic import ValidationError
from pypdf import PdfReader
from fastapi import HTTPException
from app.services import presentation_notes as notes, pre_estimate_v2 as pre, final_estimate_layout as final
from app.services.proposal_display import presentation_view, select_display_options
from app.services.pdf_optimization import render_for_user
from app.services.proposal_brands import select_brand
from app.services.final_pricing import quote
from app.core.config import settings
from app.api.v1 import estimates
from test_zone_ranges import fixture, OWNER, USER, OTHER
from test_final_layout import AuditedCanvas

class Notes(TestCase):
    def test_validation_permissions_and_immutable_views(self):
        for value in ({'notes':['']},{'notes':['x'*1001]},{'notes':['x']*21},{'notes':[123]},{'notes':['bad\x00text']},{'notes':['ok'],'price':10}):
            with self.assertRaises(ValidationError):notes.NotesInput(**value)
        e=fixture();before=deepcopy(e)
        with patch.object(settings,'ACCESS_MANAGER_USER_ID',OWNER):
            notes.select_notes(e,e.zones[0],notes.NotesInput(notes=[' Bench is not included ']))
            self.assertEqual(notes.notes_for(e,e.zones[0]),['Bench is not included'])
            self.assertIs(notes.presentation_view(e,OTHER),e)
            view=notes.presentation_view(e,USER)
            self.assertIsNot(view,e)
            self.assertEqual(view.zones[0]._presentation_notes,['Bench is not included'])
            self.assertFalse(hasattr(e.zones[0],'_presentation_notes'))
            inactive=O(id=OWNER,is_active=False)
            self.assertIs(notes.presentation_view(e,inactive),e)
            self.assertFalse(notes.available(O(id=OWNER,is_active=True,_portal_profile={'owner':False,'module':'estimating'})))
        self.assertEqual(e.line_items,before.line_items)
        self.assertEqual(e.zones,before.zones)
        self.assertEqual(quote(e),quote(before))

    def test_real_database_branch_inheritance_override_and_reload(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.core.database import Base
        from app.models.estimate import Estimate,EstimateZone,LineItem
        from app.services.estimate_branches import switch_mode,synchronize,loaded
        from test_estimate_branches import AsyncSessionAdapter
        engine=create_engine('sqlite://');Base.metadata.create_all(engine)
        self.addCleanup(engine.dispose)
        with Session(engine,expire_on_commit=False) as session:
            e=Estimate(id=uuid.uuid4(),user_id=uuid.uuid4(),type='pre',subtotal=100,final_total=100)
            z=EstimateZone(id=uuid.uuid4(),estimate_id=e.id,label='Room')
            session.add_all([e,z,LineItem(id=uuid.uuid4(),estimate_id=e.id,zone_id=z.id,name='Panels',total_price=100)])
            session.commit()
            notes.select_notes(e,z,notes.NotesInput(notes=['Bench is not included']));session.commit()
            db=AsyncSessionAdapter(session)
            async def verify():
                f=await switch_mode(db,await loaded(db,e.id),'final')
                self.assertEqual(notes.notes_for(f,f.zones[0]),['Bench is not included'])
                notes.select_notes(e,z,notes.NotesInput(notes=['Updated Pre note']));session.commit()
                f=await synchronize(db,f);session.commit()
                self.assertEqual(notes.notes_for(f,f.zones[0]),['Updated Pre note'])
                notes.select_notes(f,f.zones[0],notes.NotesInput(notes=[]));session.commit()
                notes.select_notes(e,z,notes.NotesInput(notes=['Another Pre note']));session.commit()
                f=await synchronize(db,f);session.commit();session.expire_all()
                f=await loaded(db,f.id)
                self.assertEqual(notes.notes_for(f,f.zones[0]),[])
                self.assertEqual(f.subtotal,Decimal('100'))
                self.assertEqual(f.final_total,Decimal('100'))
            asyncio.run(verify())

    def test_pdf_geometry_descriptions_notes_and_account_isolation(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(settings,'ACCESS_MANAGER_USER_ID',OWNER):
            path=Path(directory)/'notes.pdf'
            for mode,renderer in [('pre',pre.generate_pre_estimate),('final',final.generate_final_client)]:
                for brand in ('wallpanels','verona'):
                    for calculations in (False,True):
                        for count in (1,7):
                            e=fixture(1);e.type=mode
                            # More notes than fit on one page exercises continuation.
                            values=['Bench is not included']+[f'Note {n}: '+('Custom finishing and installation by the client. '*10) for n in range(count-1)]
                            e.zones[0].line_items[0].description='Description retained for client review'
                            notes.select_notes(e,e.zones[0],notes.NotesInput(notes=values))
                            select_brand(e,brand);select_display_options(e,{'show_calculations':calculations})
                            before=deepcopy(e)
                            AuditedCanvas.records=[];AuditedCanvas.rules=[];AuditedCanvas.pictures=[]
                            def render(source,target):return renderer(presentation_view(source),target)
                            with patch.object(renderer.__globals__['canvas'],'Canvas',AuditedCanvas):render_for_user(USER,render,e,path)
                            text=' '.join(p.extract_text() for p in PdfReader(path).pages)
                            self.assertEqual(text.count('Bench is not included'),1)
                            self.assertIn('Description retained',text)
                            for n in range(count-1):self.assertEqual(text.count(f'Note {n}:'),1)
                            self.assertEqual(e,before)
                            records=AuditedCanvas.records
                            for a in records:
                                if a[0]==1:continue
                                self.assertGreaterEqual(a[1],40,a)
                                self.assertLessEqual(a[3],(pre.W if mode=='pre' else final.W)-10,a)
                                self.assertGreaterEqual(a[2],32,a)
                                for b in records:
                                    if a is b or a[0]!=b[0]:continue
                                    self.assertFalse(min(a[3],b[3])-max(a[1],b[1])>1 and min(a[4],b[4])-max(a[2],b[2])>1,(mode,brand,count,a,b))
                            for record in [a for a in records if 'Bench is not' in a[-1] or a[-1].startswith('Note ')]:
                                for b in [x for x in records if x[0]==record[0] and '$' in x[-1]]:
                                    self.assertGreater(abs(record[2]-b[2]),5,(record,b))
                            render_for_user(OTHER,render,e,path)
                            other=path.read_bytes()
                            self.assertNotIn('Bench is not included',' '.join(p.extract_text() for p in PdfReader(path).pages))
                            e.pdf_layout.pop(notes.KEY)
                            render_for_user(OTHER,render,e,path)
                            self.assertEqual(other,path.read_bytes())

class Endpoints(IsolatedAsyncioTestCase):
    async def test_notes_gate_revision_flow_and_unchanged_prices(self):
        e=fixture();db=O(commit=AsyncMock())
        with patch.object(settings,'ACCESS_MANAGER_USER_ID',OWNER),patch.object(estimates,'load_estimate',new=AsyncMock(return_value=e)) as load:
            with self.assertRaises(HTTPException) as denied:await estimates.update_presentation_notes(e.id,e.zones[0].id,notes.NotesInput(notes=['Note']),db,OTHER)
            self.assertEqual(denied.exception.status_code,403);load.assert_not_awaited()
            await estimates.update_presentation_notes(e.id,e.zones[0].id,notes.NotesInput(notes=['Note']),db,USER)
            self.assertEqual(notes.notes_for(e,e.zones[0]),['Note'])
            db.commit.assert_awaited_once()
            e.type='quick'
            with self.assertRaises(HTTPException):await estimates.update_presentation_notes(e.id,e.zones[0].id,notes.NotesInput(notes=[]),db,USER)
