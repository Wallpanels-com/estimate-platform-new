"""Lossless PDF packing. Never resample, quantize, or JPEG-encode an image."""

from io import BytesIO
import struct

from PIL import Image, ImageOps
from reportlab.lib.utils import ImageReader
from pypdf.generic import DictionaryObject, NameObject, NumberObject


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
        image = Image.frombytes('RGB' if channels == 3 else 'L', (width, height), raw)
        png = BytesIO()
        image.save(png, format='PNG', compress_level=6)
        data = png.getvalue()
        offset, chunks = 8, []
        while offset < len(data):
            length = struct.unpack('>I', data[offset:offset + 4])[0]
            if data[offset + 4:offset + 8] == b'IDAT':
                chunks.append(data[offset + 8:offset + 8 + length])
            offset += length + 12
        packed = b''.join(chunks)
        if len(packed) >= len(obj._data):
            continue
        # Verify the PDF decoder reproduces the original samples before replacing.
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
        if candidate.get_data() != raw:
            raise ValueError('Lossless PDF image verification failed')
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
    # Keep source resources: pruning shared ICC profiles can invalidate some PDFs.
    writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=False)
