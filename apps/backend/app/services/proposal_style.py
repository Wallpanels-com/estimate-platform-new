"""Shared approved artwork and Arial typography; no pricing or model writes."""
from functools import lru_cache
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image

ASSETS = Path(__file__).resolve().parents[2] / 'assets/proposals'
BACKGROUND = ASSETS / 'proposal-background.png'
PRE_TITLE = ASSETS / 'pre-shared-title.png'
FINAL_TITLE = ASSETS / 'final-title-template.png'

def fonts():
    from .pre_estimate_v1 import FONT_LOCK, FONTS
    with FONT_LOCK:
        for weight, file in [('Regular','Arial.ttf'),('Medium','Arial-Bold.ttf'),('Bold','Arial-Bold.ttf')]:
            name, path = 'WP-'+weight, str(FONTS / file)
            if name not in pdfmetrics.getRegisteredFontNames() or getattr(pdfmetrics.getFont(name).face, 'filename', None) != path:
                # ReportLab ignores re-registration of an existing dynamic alias.
                # Legacy V1 may have initialized WP-* before the active renderer.
                pdfmetrics._fonts.pop(name, None)
                pdfmetrics.registerFont(TTFont(name, path))

@lru_cache(maxsize=16)
def _artwork_size(path, modified, size):
    with Image.open(path) as image:
        return image.size


def contained(c, path, x, y, w, h):
    # Filename-based XObjects let ReportLab reuse immutable artwork on every
    # page of this document without repeatedly decoding and hashing its pixels.
    # Cache dimensions only; decoded customer images never accumulate in RAM.
    path = Path(path)
    stat = path.stat()
    iw, ih = _artwork_size(str(path), stat.st_mtime_ns, stat.st_size)
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(str(path), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, mask='auto')


def background(c, width, height):
    try:
        contained(c, BACKGROUND, 0, 0, width, height)
    except (OSError, ValueError) as error:
        raise ValueError("The proposal background is missing or damaged.") from error

def pre_title(c, width, height):
    try:
        contained(c, PRE_TITLE, 0, 0, width, height)
    except (OSError, ValueError) as error:
        raise ValueError("The shared Pre-estimate cover is missing or damaged.") from error

def final_title(c, estimate, width, height, template=FINAL_TITLE):
    contained(c, template, 0, 0, width, height)
    photos = list(getattr(estimate, 'images', []) or [])
    for zone in getattr(estimate, 'zones', []) or []:
        photos.extend(getattr(zone, 'images', []) or [])
    chosen = next((p for p in photos if str(p.id) == str(getattr(estimate, 'cover_image_id', None))), None)
    if chosen is None:
        chosen = next(iter(photos), None)
    if chosen:
        # Fill only the title's photo frame with a centered crop; zone photos
        # retain their existing uncropped fit. Original uploaded bytes stay intact.
        from .pdf_optimization import image_reader
        image = image_reader(chosen.file_path)
        iw, ih = image.getSize()
        x, y, w, h = 0, height * 142 / 1701, width * 1486 / 3024, height * 1415 / 1701
        scale = max(w / iw, h / ih)
        c.saveState()
        clip = c.beginPath()
        clip.rect(x, y, w, h)
        c.clipPath(clip, stroke=0, fill=0)
        c.drawImage(image, x + (w - iw * scale) / 2, y + (h - ih * scale) / 2, iw * scale, ih * scale, mask='auto')
        c.restoreState()


def brand(c, width, height):
    logo_width = width * 0.11
    contained(c, ASSETS / 'proposal-logo.png', width * 0.86, height * 0.025, logo_width, logo_width / 3)
