"""Explicit active-staff sync: cache public Telegram avatars, never sign in or search phones."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re
from threading import RLock
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from PIL import Image

MAX_IMAGE = 2 * 1024 * 1024
MAX_HTML = 256 * 1024
_lock = RLock()
_index_cache = {}


def username(contact):
    match = re.search(r'(?<![\w.%+-])@([A-Za-z0-9_]{3,32})\b', contact or '')
    return match[1].lower() if match else None


class ProfileMeta(HTMLParser):
    def __init__(self):
        super().__init__()
        self.photo = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('property') == 'og:image':
            self.photo = attrs.get('content')


def safe_photo_url(url):
    if not url or len(url) > 4096:
        return False
    parsed = urlsplit(url)
    try:
        return (parsed.scheme == 'https' and bool(re.fullmatch(r'cdn[0-9]+\.telesco\.pe', parsed.hostname or ''))
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and parsed.path.startswith('/file/') and not parsed.fragment)
    except ValueError:
        return False


def limited_get(client, url, limit):
    with client.stream('GET', url, follow_redirects=False) as response:
        response.raise_for_status()
        chunks = bytearray()
        for chunk in response.iter_bytes():
            chunks.extend(chunk)
            if len(chunks) > limit:
                raise ValueError('Avatar response is too large')
        return bytes(chunks)


def fetch_avatar(handle, client):
    if not handle or not re.fullmatch(r'[a-z0-9_]{3,32}', handle):
        return None
    page = ProfileMeta()
    page.feed(limited_get(client, 'https://t.me/' + handle, MAX_HTML).decode('utf-8', errors='replace'))
    # Telegram's generic logo and arbitrary redirected/external URLs are never portraits.
    if not safe_photo_url(page.photo):
        return None
    data = limited_get(client, page.photo, MAX_IMAGE)
    with Image.open(BytesIO(data)) as image:
        mime = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}.get(image.format)
        if not mime or image.width * image.height > 20_000_000:
            raise ValueError('Unsupported avatar image')
        image.verify()
    return data, mime


def read_index(root):
    path = Path(root) / 'staff-avatars' / 'index.json'
    try:
        stamp = path.stat().st_mtime_ns
        with _lock:
            cached = _index_cache.get(str(path))
            if cached and cached[0] == stamp:
                return cached[1]
            value = json.loads(path.read_text())
            if not isinstance(value, dict):
                return {}
            _index_cache[str(path)] = (stamp, value)
            return value
    except (OSError, ValueError):
        return {}


def avatar_entry(person, root):
    entry = read_index(root).get(str(person.id))
    if not isinstance(entry, dict) or entry.get('username') != username(person.fields.get('F', '')):
        return None
    digest = entry.get('sha256', '')
    if not re.fullmatch(r'[a-f0-9]{64}', digest) or entry.get('mime') not in ('image/jpeg', 'image/png', 'image/webp'):
        return None
    path = Path(root) / 'staff-avatars' / f'{UUID(str(person.id))}-{digest}.image'
    return (entry, path) if path.is_file() else None


def sync_active(people, root):
    """Only called explicitly. No Telegram requests on directory or image reads."""
    selected = sorted((p for p in people if p.status == 'active'), key=lambda p: (p.name.casefold(), str(p.id)))
    folder = Path(root) / 'staff-avatars'
    folder.mkdir(parents=True, exist_ok=True)
    def download(person):
        handle = username(person.fields.get('F', ''))
        if not handle:
            return person, None, None, 'no_username'
        try:
            with httpx.Client(timeout=httpx.Timeout(8), headers={'User-Agent': 'WallPanels-Staff-Avatar/1.0'}, trust_env=False) as client:
                result = fetch_avatar(handle, client)
            return person, handle, result, 'saved' if result else 'not_public'
        except (httpx.HTTPError, ValueError, OSError, Image.DecompressionBombError):
            return person, handle, None, 'unavailable'
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(download, selected))
    with _lock:
        index = dict(read_index(root))
        for person, handle, result, status in results:
            if status in ('no_username', 'not_public'):
                index.pop(str(person.id), None)
            if result:
                data, mime = result
                digest = sha256(data).hexdigest()
                target = folder / f'{UUID(str(person.id))}-{digest}.image'
                temporary = target.with_suffix('.tmp')
                temporary.write_bytes(data)
                temporary.replace(target)
                index[str(person.id)] = {'username': handle, 'sha256': digest, 'mime': mime}
        temporary = folder / 'index.tmp'
        temporary.write_text(json.dumps(index))
        temporary.replace(folder / 'index.json')
        # These are derived avatar cache files only, never uploaded employee documents.
        referenced = {f"{ident}-{entry.get('sha256')}.image" for ident, entry in index.items() if isinstance(entry, dict)}
        for cached in folder.glob('*.image'):
            if cached.name not in referenced:
                cached.unlink(missing_ok=True)
    return [{'id': str(person.id), 'name': person.name, 'status': status} for person, _, _, status in results]
