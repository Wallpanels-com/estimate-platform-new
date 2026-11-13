"""Approved export optimization for all accounts, with unchanged source images."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace as Obj
from unittest import TestCase
from unittest.mock import patch
import tempfile
import uuid
from PIL import Image, ImageCms
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from app.services import pdf_optimization as packing
from app.api.v1 import pdf
from app.core.config import settings

class PhotoOptimization(TestCase):
    def test_account_isolation_originals_artwork_png_and_concurrency(self):
        owner = Obj(id=uuid.uuid4(), is_active=True)
        other = Obj(id=uuid.uuid4(), is_active=True)
        with tempfile.TemporaryDirectory() as folder, patch.object(settings, 'PDF_PHOTO_OPTIMIZATION_ENABLED', True):
            photo = Path(folder) / 'photo.jpg'
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
            Image.effect_noise((3000, 1800), 30).convert('RGB').save(photo, quality=100, icc_profile=profile)
            original = photo.read_bytes()
            art = Path(folder) / 'art.jpg'; art.write_bytes(original)
            png = Path(folder) / 'drawing.png'; Image.new('RGBA', (3000, 40)).save(png)
            est = Obj(images=[], zones=[Obj(images=[Obj(file_path=photo), Obj(file_path=png)])])
            def render(est, _):
                self.assertEqual(packing.image_reader(art).getSize(), (3000, 1800))
                self.assertEqual(packing.image_reader(png).getSize(), (3000, 40))
                out = BytesIO(); canvas = Canvas(out, invariant=1)
                canvas.drawImage(packing.image_reader(photo), 0, 0, 500, 300)
                canvas.save()
                page = PdfReader(out).pages[0]
                image = next(iter(page['/Resources']['/XObject'].values())).get_object()
                return image['/Width'], image.get_data()
            with ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(packing.render_for_user, owner, render, est, None)
                b = pool.submit(packing.render_for_user, other, render, est, None)
                reduced, other_result = a.result(), b.result()
            self.assertEqual(reduced[0], 2560)
            self.assertLess(len(reduced[1]), len(original))
            self.assertEqual(Image.open(BytesIO(reduced[1])).info['icc_profile'], profile)
            self.assertEqual(other_result, reduced)
            with patch.object(settings, 'PDF_PHOTO_OPTIMIZATION_ENABLED', False):
                self.assertEqual(packing.render_for_user(other, render, est, None), (3000, original))
            self.assertEqual(photo.read_bytes(), original)
            self.assertIsNone(packing._photo_export.get())
            def broken(*args): raise ValueError('render failed')
            with self.assertRaises(ValueError): packing.render_for_user(owner, broken, est, None)
            self.assertIsNone(packing._photo_export.get())
            self.assertFalse(packing.photo_optimization_enabled(Obj(id=owner.id, is_active=False)))
        with patch.object(settings, 'PDF_PHOTO_OPTIMIZATION_ENABLED', False):
            self.assertFalse(packing.photo_optimization_enabled(owner))

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
class OptimizedDelivery(IsolatedAsyncioTestCase):
    async def test_same_account_policy_for_preview_download_both_modes(self):
        owner = Obj(id=uuid.uuid4(), is_active=True)
        est = Obj(type='pre', title='Fixture', client_name='Fixture', images=[], zones=[])
        db = Obj(execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: est)))
        def renderer(source, path):
            self.assertIsNotNone(packing._photo_export.get())
            path = Path(path)
            if path.is_dir(): path = path / 'fixture.pdf'
            path.write_bytes(b'%PDF-test')
            return str(path)
        with patch.object(settings, 'PDF_PHOTO_OPTIMIZATION_ENABLED', True), patch.object(pdf, 'generate_pre_estimate', renderer), patch.object(pdf, 'generate_final_estimate', renderer):
            for user in (owner, Obj(id=uuid.uuid4(), is_active=True)):
                for endpoint in (pdf.pre_estimate, pdf.final_estimate):
                    for download in (False, True):
                        response = await endpoint(uuid.uuid4(), download, db, user)
                        self.assertEqual(response.headers['x-pdf-photo-mode'], 'optimized-2560-q95')
                        await response.background()
