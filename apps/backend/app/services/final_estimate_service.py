"""Shared lossless proposal assembly; client slides followed by 13 corporate pages."""
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import tempfile
import uuid

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import ArrayObject, DictionaryObject, RectangleObject, StreamObject

from app.services.final_estimate_layout import generate_final_client
from app.services.pdf_optimization import optimize

ASSET_DIRECTORY = Path(__file__).resolve().parents[2] / 'assets' / 'proposals'
COMPANY_PDF = ASSET_DIRECTORY / 'company-slides.pdf'
COMPANY_MANIFEST = ASSET_DIRECTORY / 'company-slides.json'
COMPANY_PAGE_COUNT = 13


class FinalEstimatePdfError(RuntimeError):
    """Safe, actionable message that the API can show to the user."""


@dataclass
class CompanySlides:
    reader: PdfReader
    digest: str
    signatures: list[str]
    content_hashes: set[str]


def _content_hash(page):
    content = page.get_contents()
    return sha256(content.get_data() if content is not None else b'').hexdigest()


def _resource_signature(value, cache, active):
    """Compare resource values, not PDF object numbers; never re-encode images."""
    value = value.get_object() if hasattr(value, 'get_object') else value
    if not isinstance(value, (DictionaryObject, ArrayObject)):
        return str(value)
    key = id(value)
    if key in cache:
        return cache[key]
    if key in active:
        return 'cycle'
    active.add(key)
    if isinstance(value, DictionaryObject):
        # Compare decoded content: lossless packing may change filters, never pixels.
        ignored = ('/Length', '/P', '/Filter', '/DecodeParms') if isinstance(value, StreamObject) else ('/Length', '/P')
        data = {str(k): _resource_signature(v, cache, active)
                for k, v in sorted(value.items()) if str(k) not in ignored}
        if isinstance(value, StreamObject):
            data['stream-sha256'] = sha256(value.get_data()).hexdigest()
    else:
        data = [_resource_signature(v, cache, active) for v in value]
    result = sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    active.remove(key)
    cache[key] = result
    return result


def page_signature(page):
    data = {
        'media': [float(v) for v in page.mediabox],
        'crop': [float(v) for v in page.cropbox],
        'rotation': page.rotation,
        'unit': float(page.get('/UserUnit', 1)),
        'content': _content_hash(page),
        'resources': _resource_signature(page.get('/Resources', DictionaryObject()), {}, set()),
        'annotations': _resource_signature(page.get('/Annots', ArrayObject()), {}, set()),
    }
    return sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def load_company_slides(asset_path=None, manifest_path=None):
    asset_path = Path(asset_path) if asset_path is not None else COMPANY_PDF
    manifest_path = Path(manifest_path) if manifest_path is not None else COMPANY_MANIFEST
    try:
        contents = asset_path.read_bytes()
        manifest = json.loads(manifest_path.read_text())
    except OSError as error:
        raise FinalEstimatePdfError(
            'The corporate slides PDF is unavailable. Restore the company slides file to generate the presentation.'
        ) from error
    except (ValueError, UnicodeError) as error:
        raise FinalEstimatePdfError(
            'The corporate slides PDF is damaged or invalid. The presentation was not generated.'
        ) from error
    try:
        digest = sha256(contents).hexdigest()
        if not isinstance(manifest, dict) or digest != manifest.get('sha256'):
            raise ValueError('Corporate asset checksum mismatch')
        reader = PdfReader(BytesIO(contents), strict=True)
        if reader.is_encrypted:
            raise ValueError('Encrypted corporate asset')
        if len(reader.pages) != COMPANY_PAGE_COUNT or manifest.get('pages') != COMPANY_PAGE_COUNT:
            raise FinalEstimatePdfError(
                'Corporate slides must contain exactly 13 pages. Final Estimate was not generated.'
            )
        reference = reader.pages[0]
        for page in reader.pages:
            width, height = float(page.mediabox.width), float(page.mediabox.height)
            if (width <= 0 or height <= 0 or not math.isclose(width / height, 16 / 9, abs_tol=0.001)
                    or page.rotation != 0 or float(page.get('/UserUnit', 1)) != 1
                    or list(page.mediabox) != list(reference.mediabox)
                    or list(page.cropbox) != list(reference.cropbox)
                    or page.get_contents() is None):
                raise ValueError('Corporate pages must share a landscape 16:9 canvas')
        return CompanySlides(reader, digest, [page_signature(p) for p in reader.pages],
                             {_content_hash(p) for p in reader.pages})
    except FinalEstimatePdfError:
        raise
    except Exception as error:
        raise FinalEstimatePdfError(
            'The corporate slides PDF is damaged or invalid. The presentation was not generated.'
        ) from error


def _same_canvas(page, reference):
    return (page.rotation == 0 and float(page.get('/UserUnit', 1)) == 1
            and list(page.mediabox) == list(reference.mediabox)
            and list(page.cropbox) == list(reference.cropbox))


def _add_client_page(writer, page, reference):
    if _same_canvas(page, reference):
        writer.add_page(page)
        return
    if page.rotation:
        rotation_writer = PdfWriter()
        page = rotation_writer.add_page(page)
        page.transfer_rotation_to_content()
    source = page.cropbox
    target = reference.cropbox
    width, height = float(source.width), float(source.height)
    if width <= 0 or height <= 0:
        raise ValueError('Invalid client page dimensions')
    # Fit the existing page as a whole: no reflow, cropping or non-uniform scaling.
    scale = min(float(target.width) / width, float(target.height) / height)
    x = float(target.left) + (float(target.width) - width * scale) / 2 - float(source.left) * scale
    y = float(target.bottom) + (float(target.height) - height * scale) / 2 - float(source.bottom) * scale
    fitted = writer.add_blank_page(width=float(reference.mediabox.width), height=float(reference.mediabox.height))
    for box in ('mediabox', 'cropbox', 'trimbox', 'bleedbox', 'artbox'):
        setattr(fitted, box, RectangleObject(getattr(reference, box)))
    fitted.merge_transformed_page(page, Transformation((scale, 0, 0, scale, x, y)))


def compose_final_pdf(client_path, output_path, company=None):
    company = company if company is not None else load_company_slides()
    output_path = Path(output_path)
    pending = output_path.with_name(f'.{output_path.name}.{uuid.uuid4()}.tmp')
    try:
        client = PdfReader(BytesIO(Path(client_path).read_bytes()), strict=True)
        if client.is_encrypted or not len(client.pages):
            raise ValueError('Invalid client PDF')
        signatures = set(company.signatures)
        client_pages = [page for page in client.pages
                        if not (_content_hash(page) in company.content_hashes
                                and page_signature(page) in signatures)]
        if not client_pages:
            raise ValueError('The client PDF contains no unique client pages')
        writer = PdfWriter()
        reference = company.reader.pages[0]
        for page in client_pages:
            _add_client_page(writer, page, reference)
        # Corporate pages are cloned directly, preserving all source image/font streams.
        for page in company.reader.pages:
            writer.add_page(page)
        writer.add_metadata({
            '/Producer': 'WallPanels Estimate Platform',
            '/WallPanelsCompanySlidesSHA256': company.digest,
            '/WallPanelsCompanySlidesCount': str(COMPANY_PAGE_COUNT),
            '/WallPanelsClientPages': str(len(client_pages)),
        })
        output_path.parent.mkdir(parents=True, exist_ok=True)
        optimize(writer)
        writer.write(pending)
        verified = PdfReader(pending, strict=True)
        if (len(verified.pages) != len(client_pages) + COMPANY_PAGE_COUNT
                or not all(_same_canvas(page, reference) for page in verified.pages)
                or [page_signature(page) for page in verified.pages[-COMPANY_PAGE_COUNT:]] != company.signatures):
            raise ValueError('Final presentation verification failed')
        # A failed assembly never replaces an existing complete PDF or returns a partial file.
        os.replace(pending, output_path)
        return str(output_path)
    except FinalEstimatePdfError:
        raise
    except Exception as error:
        raise FinalEstimatePdfError(
            'The presentation PDF could not be assembled. No incomplete PDF was returned.'
        ) from error
    finally:
        pending.unlink(missing_ok=True)


def generate_final_estimate(estimate, output_dir):
    company = load_company_slides()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='client-slides-', dir=output_dir) as directory:
        try:
            original = generate_final_client(estimate, Path(directory) / 'client.pdf')
        except (ValueError, OSError) as error:
            raise FinalEstimatePdfError(str(error)) from error
        return compose_final_pdf(original, output_dir / f'{uuid.uuid4()}.pdf', company)
