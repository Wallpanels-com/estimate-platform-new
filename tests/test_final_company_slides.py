"""Final-only PDF assembly: exact appendix, repeat safety and readable failures."""
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/backend'))
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://unused:unused@127.0.0.1:55432/unused')
os.environ.setdefault('SECRET_KEY', 'unit-tests-only')
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from reportlab.pdfgen import canvas
from app.services import final_estimate_service as final


def make_pdf(path, count, prefix, size=(960, 540)):
    doc = canvas.Canvas(str(path), pagesize=size, invariant=1)
    for index in range(count):
        doc.setFont('Helvetica', 18)
        doc.drawString(40, 80, f'{prefix} {index + 1}')
        doc.rect(30, 30, size[0] - 60, size[1] - 60)
        doc.showPage()
    doc.save()
    return path


class FinalCompanySlides(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.asset = make_pdf(self.folder / 'company.pdf', 13, 'CORPORATE')
        self.manifest = self.folder / 'company.json'
        self.write_manifest()
        self.company = final.load_company_slides(self.asset, self.manifest)
        self.client = make_pdf(self.folder / 'client.pdf', 2, 'CLIENT', (792, 612))

    def write_manifest(self):
        self.manifest.write_text(json.dumps({'pages': 13, 'sha256': sha256(self.asset.read_bytes()).hexdigest()}))

    def test_order_count_format_vectors_and_source_preservation(self):
        before = sha256(self.asset.read_bytes()).hexdigest()
        output = self.folder / 'final.pdf'
        final.compose_final_pdf(self.client, output, self.company)
        reader = PdfReader(output, strict=True)
        self.assertEqual(len(reader.pages), 15)
        self.assertIn('CLIENT 1', reader.pages[0].extract_text())
        self.assertIn('CLIENT 2', reader.pages[1].extract_text())
        for index, page in enumerate(reader.pages[2:]):
            self.assertIn(f'CORPORATE {index + 1}', page.extract_text())
            self.assertEqual(final.page_signature(page), self.company.signatures[index])
        for page in reader.pages:
            self.assertEqual(tuple(page.mediabox), (0, 0, 960, 540))
        matrix = next(args for args, op in reader.pages[0].get_contents().operations if op == b'cm')
        self.assertAlmostEqual(float(matrix[0]), float(matrix[3]))
        self.assertEqual(float(matrix[1]), 0)
        self.assertEqual(float(matrix[2]), 0)
        self.assertEqual(sha256(self.asset.read_bytes()).hexdigest(), before)

    def test_repeated_assembly_and_existing_full_or_partial_appendices(self):
        output = self.folder / 'final.pdf'
        final.compose_final_pdf(self.client, output, self.company)
        final.compose_final_pdf(output, output, self.company)
        self.assertEqual(len(PdfReader(output).pages), 15)
        for count in (5, 13, 26):
            writer = PdfWriter()
            writer.append(output)
            for index in range(count):
                writer.add_page(self.company.reader.pages[index % 13])
            doubled = self.folder / f'repeated-{count}.pdf'
            writer.write(doubled)
            final.compose_final_pdf(doubled, doubled, self.company)
            reader = PdfReader(doubled)
            self.assertEqual(len(reader.pages), 15)
            self.assertEqual([final.page_signature(p) for p in reader.pages[-13:]], self.company.signatures)

    def test_rotated_cropped_client_page_keeps_all_visible_content(self):
        make_pdf(self.client, 1, 'CLIENT', (612, 792))
        reader = PdfReader(self.client)
        page = reader.pages[0]
        page.cropbox = RectangleObject((20, 20, 600, 780))
        page.rotate(90)
        writer = PdfWriter()
        writer.add_page(page)
        rotated = self.folder / 'rotated.pdf'
        writer.write(rotated)
        final.compose_final_pdf(rotated, self.folder / 'fitted.pdf', self.company)
        fitted = PdfReader(self.folder / 'fitted.pdf').pages[0]
        self.assertEqual(fitted.rotation, 0)
        self.assertEqual(tuple(fitted.mediabox), (0, 0, 960, 540))
        self.assertIn('CLIENT 1', fitted.extract_text())

    def test_missing_damaged_wrong_count_and_wrong_format_fail_closed(self):
        with self.assertRaisesRegex(final.FinalEstimatePdfError, 'unavailable'):
            final.load_company_slides(self.folder / 'missing.pdf', self.manifest)
        self.asset.write_bytes(b'%PDF-damaged')
        with self.assertRaisesRegex(final.FinalEstimatePdfError, 'damaged'):
            final.load_company_slides(self.asset, self.manifest)
        make_pdf(self.asset, 12, 'CORPORATE')
        self.write_manifest()
        with self.assertRaisesRegex(final.FinalEstimatePdfError, 'exactly 13'):
            final.load_company_slides(self.asset, self.manifest)
        make_pdf(self.asset, 13, 'CORPORATE', (612, 792))
        self.write_manifest()
        with self.assertRaisesRegex(final.FinalEstimatePdfError, 'damaged'):
            final.load_company_slides(self.asset, self.manifest)

    def test_missing_asset_prevents_client_render_and_failed_merge_preserves_complete_file(self):
        renderer = Mock()
        with patch.object(final, 'COMPANY_PDF', self.folder / 'missing.pdf'), patch.object(final, 'generate_final_client', renderer):
            with self.assertRaises(final.FinalEstimatePdfError):
                final.generate_final_estimate(object(), self.folder / 'generation')
        renderer.assert_not_called()
        output = self.folder / 'complete.pdf'
        output.write_bytes(b'existing-complete-file')
        self.client.write_bytes(b'not a PDF')
        with self.assertRaises(final.FinalEstimatePdfError):
            final.compose_final_pdf(self.client, output, self.company)
        self.assertEqual(output.read_bytes(), b'existing-complete-file')
        self.assertFalse(list(self.folder.glob('*.tmp')))

    def test_same_client_snapshot_produces_identical_preview_and_download_bytes(self):
        left, right = self.folder / 'preview.pdf', self.folder / 'download.pdf'
        final.compose_final_pdf(self.client, left, self.company)
        final.compose_final_pdf(self.client, right, self.company)
        self.assertEqual(left.read_bytes(), right.read_bytes())

    def test_pinned_company_asset_is_the_original_thirteen_page_file(self):
        company = final.load_company_slides()
        self.assertEqual(len(company.reader.pages), 13)
        self.assertEqual(company.digest, 'a5ccab103eb00ec97bab802f5cbc07347f2b14f451695ce716ed61c7354cbb55')
