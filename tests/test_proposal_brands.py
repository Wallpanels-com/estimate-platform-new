"""Separate brand assets, immutable quotes, persistent selection and appendix safety."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as O
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from datetime import date
from decimal import Decimal
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'apps/backend'), str(ROOT / 'tests')]
from pypdf import PdfReader
from PIL import Image
from pydantic import ValidationError
from test_final_layout import estimate, zone
from app.services import proposal_brands as brands
from app.services import final_estimate_service as final
from app.services.pre_estimate_service import generate_pre_estimate
from app.api.v1 import estimates


class BrandSelection(TestCase):
    def test_default_validation_and_merge_preserve_other_layout_settings(self):
        est = O(pdf_layout={'final_zone_photos': {'zone': 2}, 'other': True})
        self.assertEqual(brands.brand_key(est), 'wallpanels')
        brands.select_brand(est, 'verona')
        self.assertEqual(est.pdf_layout, {'final_zone_photos': {'zone': 2}, 'other': True, 'proposal_brand': 'verona'})
        self.assertEqual(brands.initial_layout(est), {'proposal_brand': 'verona'})
        with self.assertRaises(ValueError): brands.select_brand(est, '../outside')
        with self.assertRaises(ValidationError): estimates.ProposalBrandUpdate(brand='unknown')
        brands.select_brand(est, 'wallpanels')
        self.assertIsNone(brands.initial_layout(est))
        for invalid in (None, {}, {'proposal_brand': []}, {'proposal_brand': 'unknown'}):
            self.assertEqual(brands.brand_key(O(pdf_layout=invalid)), 'wallpanels')

    def test_brand_appendix_is_pinned_and_verona_logo_has_real_alpha(self):
        company = final.load_company_slides(brand='verona')
        self.assertEqual(len(company.reader.pages), 29)
        self.assertEqual(company.brand, 'verona')
        self.assertEqual(company.digest, '7f9145682ff27ac7fccd677f1cb04da7ed28d5ea10cc415012a2edcb2f9a44db')
        with Image.open(brands.profile('verona').assets / 'proposal-logo.png') as logo:
            self.assertEqual(logo.mode, 'RGBA')
            self.assertGreaterEqual(logo.width, 2000)
            self.assertEqual(logo.getchannel('A').getextrema(), (0, 255))

    def test_both_brands_pre_final_preserve_data_prices_and_exact_appendices(self):
        with TemporaryDirectory() as folder:
            folder = Path(folder)
            photo = folder / 'photo.png'
            Image.new('RGB', (90, 120), '#294f71').save(photo)
            est = estimate([zone(count=3, images=[O(id='photo', slot=1, file_path=str(photo))])])
            est.prepared_by = 'Employee'; est.estimate_date = date(2026, 10, 31)
            est.markup_pct = Decimal(15); est.discount_pct = Decimal(7)
            for item in est.line_items: item.calc_type = 'sf'; item.unit = 'SF'; item.zone_id = est.zones[0].id
            texts = {}
            for brand in brands.BRANDS:
                brands.select_brand(est, brand)
                company = final.load_company_slides(brand=brand)
                before = deepcopy(est)
                for mode in ('pre', 'final'):
                    output = folder / f'{brand}-{mode}.pdf'
                    path = generate_pre_estimate(est, output) if mode == 'pre' else final.generate_final_estimate(est, folder)
                    reader = PdfReader(path, strict=True)
                    count = brands.profile(brand).company_pages
                    self.assertEqual(reader.metadata['/WallPanelsCompanySlidesCount'], str(count))
                    self.assertEqual(reader.metadata['/WallPanelsProposalBrand'], brand)
                    self.assertEqual([final.page_signature(p) for p in reader.pages[-count:]], company.signatures)
                    texts[brand, mode] = [p.extract_text() for p in reader.pages[:-count]]
                    if mode == 'pre': self.assertIn('Project Overview', texts[brand, mode][1])
                    title = brands.profile(brand).assets / ('pre-shared-title.png' if mode == 'pre' else 'final-title-template.png')
                    with Image.open(title) as original:
                        embedded = next(i.image for i in reader.pages[0].images if i.image.size == original.size)
                        self.assertEqual(embedded.convert('RGB').tobytes(), original.convert('RGB').tobytes())
                    logo = brands.profile(brand).assets / 'proposal-logo.png'
                    other_logo = brands.profile('wallpanels' if brand == 'verona' else 'verona').assets / 'proposal-logo.png'
                    with Image.open(logo) as own, Image.open(other_logo) as other:
                        sizes = [i.image.size for i in reader.pages[1].images]
                        self.assertIn(own.size, sizes)
                        self.assertNotIn(other.size, sizes)
                    # Reassembly never duplicates the selected company's appendix.
                    final.compose_final_pdf(path, folder / 'again.pdf', company)
                    self.assertEqual(len(PdfReader(folder / 'again.pdf').pages), len(reader.pages))
                    self.assertEqual(est, before)
            for mode in ('pre', 'final'):
                self.assertEqual(texts['wallpanels', mode], texts['verona', mode])

    def test_missing_or_damaged_verona_asset_fails_closed_without_affecting_wallpanels(self):
        with TemporaryDirectory() as directory:
            missing = Path(directory) / 'missing.pdf'
            with self.assertRaises(final.FinalEstimatePdfError):
                final.load_company_slides(missing, brand='verona')
            missing.write_bytes(b'not a pdf')
            with self.assertRaises(final.FinalEstimatePdfError):
                final.load_company_slides(missing, brand='verona')
        self.assertEqual(len(final.load_company_slides().reader.pages), 25)


class BrandPersistence(IsolatedAsyncioTestCase):
    async def test_endpoint_changes_only_brand_and_attribution(self):
        est = O(pdf_layout={'final_zone_photos': {'zone': 2}}, subtotal=Decimal(100), final_total=Decimal(100), markup_pct=15, discount_pct=7, prepared_by='Original')
        db = O(commit=AsyncMock()); user = O(name='Employee', email='employee@local')
        with patch.object(estimates, 'load_estimate', new=AsyncMock(return_value=est)):
            result = await estimates.update_proposal_brand(uuid.uuid4(), estimates.ProposalBrandUpdate(brand='verona'), db, user)
        self.assertIs(result, est)
        self.assertEqual(est.pdf_layout, {'final_zone_photos': {'zone': 2}, 'proposal_brand': 'verona'})
        self.assertEqual((est.subtotal, est.final_total, est.markup_pct, est.discount_pct, est.prepared_by), (Decimal(100), Decimal(100), 15, 7, 'Original'))
        self.assertEqual(est.updated_by_name, 'Employee')
        db.commit.assert_awaited_once()
