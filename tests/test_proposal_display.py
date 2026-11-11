"""Presentation visibility is persisted, read-only for pricing, and shared by brands."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as O
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
import sys, uuid
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'apps/backend'), str(ROOT / 'tests')]
from pydantic import ValidationError
from pypdf import PdfReader
from test_final_layout import estimate, zone
from app.services.proposal_display import display_options, select_display_options, presentation_view, without_calculations, calculation_detail
from app.services.proposal_brands import select_brand, initial_layout, profile
from app.services.final_pricing import quote
from app.services.final_estimate_service import generate_final_estimate, load_company_slides, page_signature
from app.services.pre_estimate_service import generate_pre_estimate
from app.api.v1 import estimates


class DisplayOptions(TestCase):
    def test_default_and_merge_preserve_existing_layout(self):
        for value in (None, {}, {'presentation_options': None}, {'presentation_options': {'show_grand_total': 'false'}}):
            est = O(pdf_layout=value)
            self.assertTrue(display_options(est).show_grand_total)
            self.assertTrue(display_options(est).show_calculations)
            self.assertIs(presentation_view(est), est)
        est = O(pdf_layout={'proposal_brand': 'verona', 'final_zone_photos': {'zone': 2}, 'other': True})
        select_display_options(est, {'show_grand_total': False})
        select_display_options(est, {'show_calculations': False})
        self.assertEqual(est.pdf_layout['final_zone_photos'], {'zone': 2})
        self.assertTrue(est.pdf_layout['other'])
        self.assertEqual(initial_layout(est), {'proposal_brand': 'verona', 'presentation_options': {'show_grand_total': False, 'show_calculations': False}})
        select_brand(est, 'wallpanels')
        self.assertFalse(display_options(est).show_calculations)

    def test_calculation_text_only_and_product_dimensions_preserved(self):
        for source, expected in (
            ('Laundry - 5 linear x 1200', 'Laundry'),
            ('Total paneling sq ft 244 x 70', 'Total paneling'),
            ('Panels (12 SF × $50.00)', 'Panels'),
            ('Install | 10 SF | Unit price: $50.00', 'Install'),
            ('Installation - 5 × $100', 'Installation'),
            ('2 x 4 lumber', '2 x 4 lumber'),
            ('Panel 2 ft x 8 ft', 'Panel 2 ft x 8 ft'),
            ('WP-SL-001 Walnut 3D', 'WP-SL-001 Walnut 3D'),
            ('Room 12', 'Room 12'),
        ):
            self.assertEqual(without_calculations(source), expected, source)

    def test_generated_calculations_reconcile_with_adjusted_cents_and_handle_manual_scope(self):
        from test_final_layout import item
        wall = item(name='Flat panels', quantity=Decimal(140), unit='SF', unit_price=Decimal(70), total_price=Decimal(9800), calc_type='sf')
        self.assertEqual(calculation_detail(wall, Decimal(9800)), '140 SF × $70.00')
        wall.quantity = Decimal('2.5'); wall.unit_price = Decimal('19.95'); wall.total_price = Decimal('49.875')
        self.assertEqual(calculation_detail(wall, Decimal('49.88')), '2.5 SF × $19.95')
        wall.quantity = Decimal(5); wall.unit = 'LF'; wall.unit_price = Decimal(1200); wall.total_price = Decimal(6000)
        for amount in (Decimal('6000.00'), Decimal('6538.88'), Decimal('0.00'), Decimal('5999.99')):
            annotation = calculation_detail(wall, amount)
            rate = Decimal(annotation.split('$')[-1].replace(',', ''))
            self.assertEqual(format(rate * wall.quantity, '.2f'), format(amount, '.2f'), annotation)
        wall.quantity = Decimal('12345.678'); wall.unit_price = Decimal('1234.56789'); wall.total_price = (wall.quantity * wall.unit_price).quantize(Decimal('.01'))
        self.assertEqual(calculation_detail(wall, Decimal('16610461.83')), '12345.678 LF · Adjusted amount')
        wall.quantity = Decimal(5); wall.unit_price = Decimal(1200)
        wall.total_price = Decimal(6500)
        self.assertEqual(calculation_detail(wall, 6500), '5 LF · Agreed amount')
        wall.calc_type = 'fixed'
        self.assertEqual(calculation_detail(wall, 6500), 'Fixed amount')
        wall.calc_type = 'lf'; wall.unit_price = None
        self.assertEqual(calculation_detail(wall, 6500), '5 LF · Agreed amount')
        wall.is_tbd = True
        self.assertEqual(calculation_detail(wall, 0), '5 LF')
        wall.quantity = None
        self.assertEqual(calculation_detail(wall, 0), '')
        wall._hide_calculations = True
        self.assertEqual(calculation_detail(wall, 0), '')

    def test_proxies_preserve_price_math_and_original_data(self):
        est = estimate([zone(count=3)])
        est.markup_pct = Decimal('17.5'); est.discount_pct = Decimal('7.25')
        est.zones[0].line_items[0].name = 'Laundry - 5 linear x 1200'
        select_display_options(est, {'show_calculations': False})
        before = deepcopy(est)
        viewed = presentation_view(est)
        self.assertEqual(viewed.zones[0].line_items[0].name, 'Laundry')
        self.assertIs(viewed.line_items[0], viewed.zones[0].line_items[0])
        original, hidden = quote(est), quote(viewed)
        for key in ('gross', 'discount', 'component_total', 'grand_total', 'manual_adjustment', 'warnings', 'errors'):
            self.assertEqual(getattr(original, key), getattr(hidden, key), key)
        self.assertEqual(est, before)

    def test_both_modes_brands_and_all_visibility_combinations_keep_exact_appendix(self):
        est = estimate([zone(count=3)])
        est.prepared_by = 'Local fixture'; est.estimate_date = date(2026, 11, 11)
        est.markup_pct = Decimal('17.5'); est.discount_pct = Decimal('7.25')
        for n, item in enumerate(est.line_items):
            item.id = uuid.uuid4(); item.zone_id = est.zones[0].id
            item.name = 'Laundry - 5 linear x 1200' if n == 0 else f'Component {n+1}'
            item.description = 'Measured finish'; item.calc_type = 'sf'; item.unit = 'SF'
        est.line_items[0].quantity = Decimal(5); est.line_items[0].unit = 'LF'
        est.line_items[0].unit_price = Decimal(1200); est.line_items[0].total_price = Decimal(6000)
        est.subtotal = est.final_total = sum(i.total_price for i in est.line_items)
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            for brand in ('wallpanels', 'verona'):
                select_brand(est, brand)
                company = load_company_slides(brand=brand)
                for total in (True, False):
                    for calculations in (True, False):
                        select_display_options(est, {'show_grand_total': total, 'show_calculations': calculations})
                        before = deepcopy(est)
                        for mode in ('pre', 'final'):
                            with self.subTest(brand=brand, mode=mode, total=total, calculations=calculations):
                                target = folder / f'{brand}-{mode}-{total}-{calculations}.pdf'
                                output = generate_pre_estimate(est, target) if mode == 'pre' else generate_final_estimate(est, folder)
                                pdf = PdfReader(output, strict=True)
                                pages = pdf.pages[:-profile(brand).company_pages]
                                text = ' '.join(' '.join(p.extract_text() for p in pages).split())
                                self.assertIn('investment summary', text.lower())
                                self.assertEqual('GRAND TOTAL' in text if mode == 'final' else 'Current Calculation Basis' in text, total)
                                self.assertNotIn('5 linear x 1200', text, 'Stale inline arithmetic is replaced by structured current fields')
                                self.assertEqual('5 LF ×' in text, calculations)
                                if calculations:
                                    expected = calculation_detail(est.line_items[0], quote(est).item_prices[str(est.line_items[0].id)]) if mode == 'final' else '5 LF × $1,113.00'
                                    self.assertIn(expected, text)
                                if mode == 'pre':
                                    self.assertEqual('×' in text, calculations)
                                    self.assertEqual('Preliminary Investment Range' in text, total)
                                self.assertIn('Component 2', text)
                                self.assertEqual([page_signature(p) for p in pdf.pages[-len(company.reader.pages):]], company.signatures)
                                self.assertEqual(est, before)


class Persistence(IsolatedAsyncioTestCase):
    async def test_validated_patch_changes_only_display_and_attribution(self):
        for body in ({}, {'show_grand_total': 'false'}, {'show_calculations': 0}, {'other': True}):
            with self.assertRaises(ValidationError): estimates.PresentationOptionsUpdate(**body)
        est = O(pdf_layout={'proposal_brand': 'verona', 'final_zone_photos': {'zone': 1}}, subtotal=Decimal(100), final_total=Decimal(100), markup_pct=15, discount_pct=7, prepared_by='Original')
        db = O(commit=AsyncMock()); user = O(name='Employee', email='local')
        with patch.object(estimates, 'load_estimate', new=AsyncMock(return_value=est)):
            result = await estimates.update_presentation_options(uuid.uuid4(), estimates.PresentationOptionsUpdate(show_grand_total=False), db, user)
        self.assertIs(result, est)
        self.assertFalse(display_options(est).show_grand_total)
        self.assertTrue(display_options(est).show_calculations)
        self.assertEqual(est.pdf_layout['final_zone_photos'], {'zone': 1})
        self.assertEqual(est.pdf_layout['proposal_brand'], 'verona')
        self.assertEqual((est.subtotal, est.final_total, est.markup_pct, est.discount_pct, est.prepared_by), (Decimal(100), Decimal(100), 15, 7, 'Original'))
        db.commit.assert_awaited_once()
