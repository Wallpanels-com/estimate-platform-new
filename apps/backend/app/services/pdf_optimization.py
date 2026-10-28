"""Lossless PDF packing. Never resample, quantize, or JPEG-encode an image."""

from io import BytesIO
import struct
from collections import OrderedDict
from hashlib import sha256
from threading import RLock
from pathlib import Path
import logging

from PIL import Image, ImageOps
from reportlab import rl_config
from reportlab.lib.utils import ImageReader
from pypdf.generic import DictionaryObject, NameObject, NumberObject

# Binary PDF streams avoid the unnecessary ASCII85 encode/decode pass. This
# changes transport encoding only, never image samples, fonts, or page content.
rl_config.useA85 = False

_packed_images = OrderedDict()
_packed_bytes = 0
_packed_lock = RLock()
_PACKED_BUDGET = 16 * 1024 * 1024
_PACKED_ENTRIES = 64


def _png_samples(raw, width, height, channels):
    """Bounded RAM cache of image streams, not PDFs; any pixel change misses it."""
    global _packed_bytes
    key = (sha256(raw).digest(), width, height, channels)
    with _packed_lock:
        if key in _packed_images:
            _packed_images.move_to_end(key)
            return _packed_images[key]
    image = Image.frombytes('RGB' if channels == 3 else 'L', (width, height), raw)
    png = BytesIO()
    image.save(png, format='PNG', compress_level=6)
    data = png.getvalue()
    # Pillow's native PNG decoder verifies samples without the slow Python PDF
    # row-predictor loop. PDF predictor wiring is covered by pixel-level tests.
    with Image.open(BytesIO(data)) as check:
        if check.tobytes() != raw:
            raise ValueError('Lossless PDF image verification failed')
    offset, chunks = 8, []
    while offset < len(data):
        length = struct.unpack('>I', data[offset:offset + 4])[0]
        if data[offset + 4:offset + 8] == b'IDAT':
            chunks.append(data[offset + 8:offset + 8 + length])
        offset += length + 12
    packed = b''.join(chunks)
    if len(packed) <= _PACKED_BUDGET:
        with _packed_lock:
            if key not in _packed_images:
                while _packed_images and (len(_packed_images) >= _PACKED_ENTRIES
                        or _packed_bytes + len(packed) > _PACKED_BUDGET):
                    _, removed = _packed_images.popitem(last=False)
                    _packed_bytes -= len(removed)
                _packed_images[key] = packed
                _packed_bytes += len(packed)
    return packed


def warm_static_images():
    """Prepare only versioned artwork once at startup, never customer PDFs."""
    backend = Path(__file__).resolve().parents[2]
    paths = [backend / 'assets/proposals/final-shared-title.png',
             backend / 'assets/proposals/zone-template-clean.png',
             backend / 'app/assets/brand/wallpanels-verona-transparent.png']
    for path in paths:
        try:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source)
                rgb = image.convert('RGB')
                _png_samples(rgb.tobytes(), *rgb.size, 3)
                if 'A' in image.getbands():
                    alpha = image.getchannel('A')
                    _png_samples(alpha.tobytes(), *alpha.size, 1)
        except (OSError, ValueError):
            # A missing optional warm-up asset must not take the platform down;
            # the exporter retains its existing actionable validation errors.
            logging.getLogger(__name__).warning('PDF asset warm-up skipped: %s', path.name)


def image_reader(path):
    """Embed an unchanged JPEG directly instead of inflating it to raw RGB."""
    with Image.open(path) as source:
        if (source.format == 'JPEG' and source.mode in ('RGB', 'L')
                and source.getexif().get(274, 1) == 1):
            return ImageReader(str(path))
        mode = 'RGBA' if 'A' in source.getbands() or 'transparency' in source.info else 'RGB'
        return ImageReader(ImageOps.exif_transpose(source).convert(mode))


def contained(c, path, x, y, w, h):
    image = image_reader(path)
    iw, ih = image.getSize()
    scale = min(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    c.drawImage(image, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, mask='auto')


def pack_images(writer):
    """Use PNG row predictors for raw 8-bit RGB/gray streams when smaller.

    Original color profiles, dimensions, alpha masks and decode arrays stay intact.
    JPEG/JPX streams are passed through. PNG packing is reversible byte for byte.
    """
    saved = 0
    for obj in list(writer._objects):
        if not isinstance(obj, DictionaryObject) or obj.get('/Subtype') != '/Image':
            continue
        filters = obj.get('/Filter', [])
        filters = [filters] if isinstance(filters, str) else filters
        if any(f not in ('/FlateDecode', '/ASCII85Decode') for f in filters):
            continue
        if obj.get('/BitsPerComponent') != 8 or obj.get('/ImageMask'):
            continue
        if isinstance(obj.get('/DecodeParms'), dict) and obj['/DecodeParms'].get('/Predictor') == 15:
            continue  # Already packed (including the verified corporate asset).
        color = obj.get('/ColorSpace')
        channels = {'/DeviceRGB': 3, '/DeviceGray': 1}.get(str(color))
        if isinstance(color, list) and color[0] == '/ICCBased':
            channels = color[1].get_object().get('/N')
        if channels not in (1, 3):
            continue
        width, height = int(obj['/Width']), int(obj['/Height'])
        raw = obj.get_data()
        if len(raw) != width * height * channels:
            continue
        packed = _png_samples(raw, width, height, channels)
        if len(packed) >= len(obj._data):
            continue
        # Encoding and pixel verification already happened in the native PNG path.
        candidate = obj.__class__()
        candidate.update(obj)
        candidate[NameObject('/Filter')] = NameObject('/FlateDecode')
        candidate[NameObject('/DecodeParms')] = DictionaryObject({
            NameObject('/Predictor'): NumberObject(15),
            NameObject('/Colors'): NumberObject(channels),
            NameObject('/BitsPerComponent'): NumberObject(8),
            NameObject('/Columns'): NumberObject(width),
        })
        candidate._data = packed
        candidate.decoded_self = None
        saved += len(obj._data) - len(packed)
        obj[NameObject('/Filter')] = candidate['/Filter']
        obj[NameObject('/DecodeParms')] = candidate['/DecodeParms']
        obj._data = packed
        obj.decoded_self = None
    return saved


def optimize(writer):
    pack_images(writer)
    for page in writer.pages:
        page.compress_content_streams()
    # ReportLab already shares repeated images and fonts within the client PDF;
    # PdfWriter shares the corporate resources during cloning. A second generic
    # deduplication pass re-decodes every PNG and adds seconds without useful gain.
