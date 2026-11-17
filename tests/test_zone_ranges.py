"""Shared account access, persisted ranges, arithmetic and measured PDF geometry."""
import sys, uuid, tempfile
from pathlib import Path
from decimal import Decimal
from copy import deepcopy
from types import SimpleNamespace as O
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import patch, AsyncMock
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'apps/backend'), str(ROOT/'tests')]
from pydantic import ValidationError
from fastapi import HTTPException
from pypdf import PdfReader
from app.services import zone_ranges as r, pre_estimate_v2 as pdf
from app.services.presentation_tax import select_tax, TaxOptions
from app.services.proposal_brands import select_brand, initial_layout
from app.services.pdf_optimization import render_for_user
from app.services.pre_estimate_service import _PreEstimateView
from app.core.config import settings
from app.api.v1 import estimates
from test_final_layout import estimate, zone, item, AuditedCanvas
OWNER = uuid.uuid4()
USER = O(id=OWNER, is_active=True, name='Owner', email='owner')
OTHER = O(id=uuid.uuid4(), is_active=True, name="Employee", email="employee", page_access=["estimates"])
RESTRICTED = O(id=uuid.uuid4(), is_active=True, page_access=["hr"])


def fixture(count=2):
    e = estimate([zone(f'Zone {n + 1}', count=1) for n in range(count)])
    e.id=uuid.uuid4();e.type='pre';e.source_estimate_id=None;e.prepared_by='Fixture';e.revision='fixture'
    for z in e.zones:
        for i in z.line_items: i.zone_id=z.id
    return e


class Ranges(TestCase):
    def test_mixed_discount_manual_tax_and_no_double_expansion(self):
        e=fixture(); e.zones[0].line_items[0].total_price=Decimal(25000);e.zones[1].line_items[0].total_price=Decimal(10000)
        e.discount_pct=10;e.markup_pct=50 # Final-only markup ignored
        r.select_range(e,e.zones[0],r.RangeOptions(enabled=True))
        data=r.snapshot(e)
        self.assertEqual((data['lower'],data['upper']),('29250.00','34875.00'))
        r.select_range(e,e.zones[0],r.RangeOptions(enabled=True,mode='manual',lower=24000,upper=26000))
        data=r.snapshot(e)
        self.assertEqual((data['lower'],data['upper']),('33000.00','35000.00'))
        select_tax(e,TaxOptions(enabled=True,rate=7))
        data=r.snapshot(e)
        self.assertEqual((data['grand_lower'],data['grand_upper']),('35310.00','37450.00'))
        select_tax(e,TaxOptions(enabled=True,mode='amount',amount=123))
        data=r.snapshot(e)
        self.assertEqual((data['grand_lower'],data['grand_upper']),('33123.00','35123.00'))
        e.zones[0].line_items[0].total_price=Decimal(30000)
        self.assertTrue(r.snapshot(e)['zones'][str(e.zones[0].id)]['stale'])
        self.assertEqual(r.snapshot(e)['lower'],'33000.00')
        r.select_range(e,e.zones[0],r.RangeOptions(enabled=True))
        self.assertFalse(r.snapshot(e)['zones'][str(e.zones[0].id)]['stale'])
        self.assertEqual(r.snapshot(e)['lower'],'33300.00')
        e.line_items.append(item(total_price=Decimal(100),zone_id=None))
        self.assertEqual(r.snapshot(e)['lower'],'33390.00')
        r.select_range(e,e.zones[0],r.RangeOptions(enabled=False))
        self.assertFalse(r.snapshot(e)['active'])
        self.assertNotIn(r.KEY,initial_layout(e)) # Final never inherits ranges

    def test_validation_and_preservation(self):
        for data in ({'enabled':'yes'},{'enabled':True,'mode':'manual'}, {'enabled':True,'mode':'manual','lower':2,'upper':1}, {'enabled':True,'lower':-1}, {'enabled':True,'upper':'NaN'}, {'enabled':True,'lower':'1.001'}):
            with self.assertRaises(ValidationError):r.RangeOptions(**data)
        e=fixture();e.pdf_layout={'proposal_brand':'verona'};before=deepcopy(e)
        r.select_range(e,e.zones[0],r.RangeOptions(enabled=True,mode='manual',lower=1,upper=1))
        self.assertEqual(e.pdf_layout['proposal_brand'],'verona')
        self.assertEqual(e.line_items,before.line_items)
        self.assertEqual(e.zones,before.zones)
        e.zones[1].line_items[0].total_price=Decimal(0)
        with self.assertRaises(ValueError):r.select_range(e,e.zones[1],r.RangeOptions(enabled=True))

    def test_shared_views_access_gates_and_untouched_final(self):
        e=fixture();before=deepcopy(e)
        with patch.object(settings,'ACCESS_MANAGER_USER_ID',OWNER):
            self.assertIs(r.presentation_view(e,USER),e)
            r.select_range(e,e.zones[0],r.RangeOptions(enabled=True))
            self.assertIsNot(r.presentation_view(e,OTHER),e)
            self.assertIs(r.presentation_view(e,RESTRICTED),e)
            inactive=O(id=OWNER,is_active=False)
            self.assertIs(r.presentation_view(e,inactive),e)
            portal=O(id=OTHER.id,is_active=True,_portal_profile={'owner':False,'module':'estimating','pages':['estimates']})
            self.assertIsNot(r.presentation_view(e,portal),e)
            portal._portal_profile['pages']=['hr']
            self.assertIs(r.presentation_view(e,portal),e)
            portal._portal_profile={'module':'hr','pages':['estimates']}
            self.assertIs(r.presentation_view(e,portal),e)
            self.assertFalse(r.available(None))
            self.assertFalse(r.available(O(id=OTHER.id,is_active=True,page_access=['quick_estimate'])))
            v=r.presentation_view(e,USER)
            self.assertIsNot(v,e)
            self.assertEqual(r.price_label(v.zones[0]),'$810.00 – $1,035.00')
            self.assertIsNone(r.price_label(e.zones[0]))
            e.type='final';self.assertIs(r.presentation_view(e,USER),e)
        self.assertEqual(e.line_items,before.line_items)

    def test_render_access_and_geometry_both_brands(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings,'ACCESS_MANAGER_USER_ID',OWNER):
            target=Path(tmp)/'trial.pdf'
            for count in (1,6,11):
                for tax in (False,True):
                    e=fixture(count)
                    e.zones[0].label='Architectural finish and cabinetry with concealed storage'
                    r.select_range(e,e.zones[0],r.RangeOptions(enabled=True,mode='manual',lower='24000',upper='26000'))
                    select_tax(e,TaxOptions(enabled=tax,rate='7'))
                    for brand in ('wallpanels','verona'):
                        select_brand(e,brand)
                        AuditedCanvas.records=[];AuditedCanvas.rules=[]
                        with patch.object(pdf.canvas,'Canvas',AuditedCanvas):
                            render_for_user(USER,pdf.generate_pre_estimate,_PreEstimateView(e),target)
                        text=' '.join(p.extract_text() for p in PdfReader(target).pages)
                        self.assertIn('$24,000.00 – $26,000.00',text)
                        self.assertIn('GRAND TOTAL' if tax else 'Grand Total / Investment Range',text)
                        records=AuditedCanvas.records
                        for a in records:
                            self.assertGreaterEqual(a[1],60,(brand,count,a))
                            self.assertLessEqual(a[3],pdf.W-40,(brand,count,a))
                            for b in records:
                                if a is b or a[0]!=b[0]:continue
                                self.assertFalse(min(a[3],b[3])-max(a[1],b[1])>.8 and min(a[4],b[4])-max(a[2],b[2])>.8,(brand,count,a,b))
                            for page,x,y,right in AuditedCanvas.rules:
                                if page==a[0]:self.assertFalse(a[2]+.8<y<a[4]-.8 and min(right,a[3])-max(x,a[1])>1,(a,y))
                        owner_bytes = target.read_bytes()
                        render_for_user(OTHER,pdf.generate_pre_estimate,_PreEstimateView(e),target)
                        self.assertEqual(owner_bytes,target.read_bytes())
                        self.assertIn('$24,000.00',' '.join(p.extract_text() for p in PdfReader(target).pages))
            # Disabled settings preserve the existing output for employees.
            e=fixture();r.select_range(e,e.zones[0],r.RangeOptions(enabled=False))
            render_for_user(OTHER,pdf.generate_pre_estimate,e,target);before=target.read_bytes()
            e.pdf_layout=None
            render_for_user(OTHER,pdf.generate_pre_estimate,e,target)
            self.assertEqual(before,target.read_bytes())


class Endpoints(IsolatedAsyncioTestCase):
    async def test_employee_can_save_owner_can_read_and_restricted_users_denied(self):
        e=fixture();db=O(commit=AsyncMock())
        with patch.object(settings,'ACCESS_MANAGER_USER_ID',OWNER), patch.object(estimates,'load_estimate',new=AsyncMock(return_value=e)) as load:
            with self.assertRaises(HTTPException) as denied:
                await estimates.update_zone_range(e.id,e.zones[0].id,r.RangeOptions(enabled=True),db,RESTRICTED)
            self.assertEqual(denied.exception.status_code,403);load.assert_not_awaited()
            await estimates.update_zone_range(e.id,e.zones[0].id,r.RangeOptions(enabled=True),db,OTHER)
            data=await estimates.get_zone_ranges(e.id,db,USER)
            self.assertTrue(data['active']);db.commit.assert_awaited_once()
            e.type='final'
            with self.assertRaises(HTTPException):await estimates.get_zone_ranges(e.id,db,USER)
