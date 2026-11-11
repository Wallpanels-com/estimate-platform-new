"""Tax is opt-in, exact to cents, saved per branch, and display-only."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from decimal import Decimal
from types import SimpleNamespace as O
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import patch, AsyncMock
import sys,uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/backend'),str(ROOT/'tests')]
from pydantic import ValidationError
from pypdf import PdfReader
from test_final_layout import estimate,zone
from app.services.presentation_tax import TaxOptions, tax_options, select_tax, breakdown, proposal_subtotal
from app.services.proposal_brands import initial_layout,select_brand
from app.services.proposal_display import select_display_options
from app.services import final_estimate_layout as final, pre_estimate_v2 as pre
from app.services.pre_estimate_service import _PreEstimateView
from app.api.v1 import estimates

class Tax(TestCase):
    def test_defaults_exact_rounding_validation_and_no_threshold_rule(self):
        e=O(pdf_layout=None)
        self.assertFalse(tax_options(e).enabled)
        self.assertEqual(breakdown(e,38600).grand_total,Decimal(38600))
        for subtotal,rate,tax,total in [('38600','7','2702','41302'),('.05','10','.01','.06'),('100000','7','7000','107000'),('100','0','0','100'),('100','100','100','200')]:
            select_tax(e,TaxOptions(enabled=True,rate=rate))
            value=breakdown(e,Decimal(subtotal))
            self.assertEqual((value.tax,value.grand_total),(Decimal(tax),Decimal(total)))
        select_tax(e,TaxOptions(enabled=True,mode='amount',amount='21.37'))
        self.assertEqual(breakdown(e,100).grand_total,Decimal('121.37'))
        for body in ({'rate':-1},{'rate':101},{'rate':'NaN'},{'amount':'Infinity'},{'amount':'1.001'},{'rate':'7.00001'},{'enabled':'true'},{'unknown':True}):
            with self.assertRaises(ValidationError): TaxOptions(**body)
        with self.assertRaises(ValueError): breakdown(e,-1)
        with self.assertRaises(ValueError): tax_options(O(pdf_layout={'presentation_tax':{'enabled':True,'rate':-1}}))

    def test_merge_inheritance_adjustments_and_source_data_are_preserved(self):
        e=estimate([zone(count=3)]);e.type='final';e.markup_pct=10;e.discount_pct=5
        e.pdf_layout={'proposal_brand':'verona','presentation_options':{'show_grand_total':False},'final_zone_photos':{'zone':2}}
        before=deepcopy(e)
        select_tax(e,TaxOptions(enabled=True,rate='7.25'))
        self.assertEqual(e.pdf_layout['final_zone_photos'],before.pdf_layout['final_zone_photos'])
        self.assertEqual(initial_layout(e)['presentation_tax'],e.pdf_layout['presentation_tax'])
        self.assertNotIn('final_zone_photos',initial_layout(e))
        base=proposal_subtotal(e);self.assertEqual(base,Decimal('2821.50'))
        self.assertEqual(breakdown(e,base).grand_total,Decimal('3026.06'))
        e.manual_override=True;e.final_total=Decimal(3000)
        self.assertEqual(proposal_subtotal(e),Decimal(3135))
        e.type='pre'
        self.assertEqual(proposal_subtotal(e),Decimal(2565))
        self.assertEqual((e.subtotal,before.subtotal),(Decimal(2700),Decimal(2700)))

    def test_disabled_tax_keeps_exact_existing_client_pdf_bytes(self):
        e=estimate([zone(count=3)])
        e.prepared_by='Fixture'
        with TemporaryDirectory() as folder:
            for brand in ('wallpanels','verona'):
                select_brand(e,brand)
                for mode,render in [('pre',pre.generate_pre_estimate),('final',final.generate_final_client)]:
                    a=Path(folder)/'a.pdf';b=Path(folder)/'b.pdf'
                    e.pdf_layout.pop('presentation_tax',None)
                    render(e,a)
                    select_tax(e,TaxOptions(enabled=False,mode='amount',amount=123))
                    render(e,b)
                    self.assertEqual(a.read_bytes(),b.read_bytes(),(brand,mode))

    def test_tax_summary_geometry_and_totals_both_modes_brands_and_hidden_state(self):
        from test_final_layout import AuditedCanvas
        from app.services.proposal_style import fonts
        fonts()
        with TemporaryDirectory() as folder:
            for count in (1,3,12,20):
                e=estimate([zone(('Architectural finishes with concealed mounting ' if count==20 else 'Area ')+str(n+1),count=1) for n in range(count)])
                e.prepared_by='Fixture';e.markup_pct=Decimal('17.5');e.discount_pct=Decimal('7.25')
                for z in e.zones:
                    for i in z.line_items:i.total_price=Decimal('123456789.12')
                e.subtotal=e.final_total=sum(i.total_price for i in e.line_items)
                select_tax(e,TaxOptions(enabled=True,rate='7'))
                for brand in ('wallpanels','verona'):
                    select_brand(e,brand)
                    for mode,render in [('pre',pre.generate_pre_estimate),('final',final.generate_final_client)]:
                        target=Path(folder)/f'{mode}.pdf';view=_PreEstimateView(e) if mode=='pre' else e
                        before=deepcopy(e)
                        AuditedCanvas.records=[];AuditedCanvas.rules=[];AuditedCanvas.pictures=[]
                        with patch.object(final.canvas if mode=='final' else pre.canvas,'Canvas',AuditedCanvas): render(view,target)
                        reader=PdfReader(target,strict=True)
                        text=' '.join(' '.join(p.extract_text() for p in reader.pages).split())
                        self.assertEqual(text.count('TAX (7%)'),1)
                        base=proposal_subtotal(O(**(vars(e)|{'type':mode})))
                        self.assertIn(f'${breakdown(e,base).grand_total:,.2f}',text)
                        records=AuditedCanvas.records
                        pages={r[0] for r in records if r[-1]=='TAX (7%)'}
                        for a in [r for r in records if r[0] in pages]:
                            self.assertGreaterEqual(a[1],60);self.assertLessEqual(a[3],(final.W if mode=='final' else pre.W)-40)
                            for b in records:
                                if a is b or a[0]!=b[0]:continue
                                self.assertFalse(min(a[3],b[3])-max(a[1],b[1])>.8 and min(a[4],b[4])-max(a[2],b[2])>.8,(mode,count,a,b))
                            for p,x,y,right in AuditedCanvas.rules:
                                if p==a[0]:self.assertFalse(a[2]+.8<y<a[4]-.8 and min(right,a[3])-max(x,a[1])>1)
                        self.assertEqual(e,before)
            select_display_options(e,{'show_grand_total':False})
            for render in (pre.generate_pre_estimate,final.generate_final_client):
                render(e,Path(folder)/'hidden.pdf')
                self.assertNotIn('TAX (7%)',' '.join(p.extract_text() for p in PdfReader(Path(folder)/'hidden.pdf').pages))

class TaxEndpoint(IsolatedAsyncioTestCase):
    async def test_endpoint_persists_only_settings_and_attribution(self):
        e=estimate([zone(count=1)]);e.id=uuid.uuid4();e.type='pre';e.source_estimate_id=None;e.revision='fixture';e.prepared_by='Original'
        before=deepcopy(e);db=O(commit=AsyncMock());user=O(name='Employee',email='local')
        with patch.object(estimates,'load_estimate',new=AsyncMock(return_value=e)):
            await estimates.update_presentation_tax(e.id,TaxOptions(enabled=True),db,user)
            data=await estimates.get_presentation_tax(e.id,db,user)
        self.assertEqual(data['options']['enabled'],True)
        self.assertEqual(data['grand_total'],'963.00')
        self.assertEqual((e.subtotal,e.final_total,e.prepared_by,e.line_items,e.zones),(before.subtotal,before.final_total,before.prepared_by,before.line_items,before.zones))
        db.commit.assert_awaited_once()
