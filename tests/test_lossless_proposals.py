"""Pixel preservation, shared appendices and Final-only markup regression checks."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from test_export_layouts import example
from test_final_company_slides import make_pdf
from app.services import final_estimate_service as assembly
from app.services import pre_estimate_service as pre
from app.services.pdf_optimization import image_reader, optimize


class LosslessProposals(TestCase):
    def test_png_predictors_preserve_all_samples_alpha_content_and_links(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            im = Image.new('RGBA', (256, 192))
            im.putdata([(x % 256, y % 256, (x + y) % 256, (x * 2) % 256)
                        for y in range(192) for x in range(256)])
            path = folder / 'photo.png'
            im.save(path)
            source = BytesIO()
            canvas = Canvas(source, pagesize=(960, 540), invariant=1)
            canvas.drawImage(image_reader(path), 10, 10, 512, 384, mask='auto')
            canvas.drawString(30, 480, 'Readable vector text')
            canvas.linkURL('https://wallpanels.com', (30, 470, 200, 490))
            canvas.showPage()
            canvas.save()
            reader = PdfReader(source)
            signature = assembly.page_signature(reader.pages[0])
            writer = PdfWriter()
            writer.append(reader)
            optimize(writer)
            packed = BytesIO()
            writer.write(packed)
            result = PdfReader(packed, strict=True)
            self.assertEqual(assembly.page_signature(result.pages[0]), signature)
            self.assertLess(len(packed.getvalue()), len(source.getvalue()))
            self.assertIn('Readable vector text', result.pages[0].extract_text())

    def test_jpeg_stream_is_copied_without_reencoding_or_downsampling(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'photo.jpg'
            Image.new('RGB', (401, 607), '#a89374').save(path, quality=94)
            source = BytesIO()
            canvas = Canvas(source)
            canvas.drawImage(image_reader(path), 10, 10, 200, 300)
            canvas.showPage()
            canvas.save()
            stream = next(iter(PdfReader(source).pages[0]['/Resources']['/XObject'].values())).get_object()
            self.assertIn('/DCTDecode', stream['/Filter'])
            self.assertEqual(stream.get_data(), path.read_bytes())
            self.assertEqual((stream['/Width'], stream['/Height']), (401, 607))

    def test_pre_versions_append_exactly_thirteen_pages_and_ignore_markup(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            corporate = make_pdf(folder / 'company.pdf', 13, 'CORPORATE')
            reader = PdfReader(corporate)
            company = assembly.CompanySlides(reader, 'fixture',
                [assembly.page_signature(p) for p in reader.pages],
                {assembly._content_hash(p) for p in reader.pages})
            for version in ('v1', 'v2'):
                estimate = example()
                estimate.markup_pct = 0
                original = deepcopy(estimate)
                with patch.object(pre, 'design_version', return_value=version), patch.object(pre, 'load_company_slides', return_value=company):
                    a, b = folder / f'{version}-a.pdf', folder / f'{version}-b.pdf'
                    pre.generate_pre_estimate(estimate, a)
                    self.assertEqual(estimate, original)
                    estimate.markup_pct = 30
                    marked = deepcopy(estimate)
                    pre.generate_pre_estimate(estimate, b)
                    self.assertEqual(estimate, marked)
                    left, right = PdfReader(a), PdfReader(b)
                    self.assertEqual(len(left.pages), len(right.pages))
                    self.assertGreater(len(left.pages), 13)
                    self.assertEqual([p.extract_text() for p in left.pages],
                                     [p.extract_text() for p in right.pages])
                    if version == 'v2':
                        self.assertEqual(a.read_bytes(), b.read_bytes())
                    self.assertEqual([assembly.page_signature(p) for p in right.pages[-13:]], company.signatures)
                    repeated = folder / f'{version}-repeated.pdf'
                    assembly.compose_final_pdf(b, repeated, company)
                    self.assertEqual(len(PdfReader(repeated).pages), len(right.pages))

    def test_missing_corporate_file_fails_before_any_pre_renderer(self):
        with patch.object(pre, 'load_company_slides', side_effect=assembly.FinalEstimatePdfError('unavailable')), patch('app.services.pre_estimate_v2.generate_pre_estimate') as render:
            with self.assertRaises(assembly.FinalEstimatePdfError):
                pre.generate_pre_estimate(example(), 'unused.pdf')
            render.assert_not_called()
