"""Public avatar fetches stay bounded, authenticated by the route, and separate from staff data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/backend'))
import json
import tempfile
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import httpx
from PIL import Image
from app.services.staff_avatars import username, safe_photo_url, fetch_avatar, sync_active, avatar_entry


def picture():
    stream = BytesIO()
    Image.new('RGB', (80, 80), '#888888').save(stream, 'JPEG')
    return stream.getvalue()


class StaffAvatarTests(unittest.TestCase):
    def test_username_only_never_phone_or_email(self):
        self.assertEqual(username('380991112233 @employee_one'), 'employee_one')
        self.assertIsNone(username('employee@example.com'))
        self.assertIsNone(username('+15550100000'))

    def test_only_official_photo_cdn_no_redirect_or_arbitrary_host(self):
        self.assertTrue(safe_photo_url('https://cdn4.telesco.pe/file/photo.jpg'))
        for url in ('http://cdn4.telesco.pe/file/a', 'https://telegram.org/img/t_logo_2x.png',
                    'https://cdn4.telesco.pe.evil.test/file/a', 'https://cdn4.telesco.pe:8080/file/a',
                    'https://user:secret@cdn4.telesco.pe/file/a', 'https://127.0.0.1/file/a'):
            self.assertFalse(safe_photo_url(url))

    def test_original_image_bytes_and_negative_profile(self):
        data = picture()
        calls = []
        def handler(req):
            calls.append(str(req.url))
            if req.url.host == 't.me':
                return httpx.Response(200, text='<meta property="og:image" content="https://cdn4.telesco.pe/file/photo.jpg">')
            return httpx.Response(200, content=data)
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            self.assertEqual(fetch_avatar('employee_one', client), (data, 'image/jpeg'))
        self.assertEqual(len(calls), 2)
        with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text='<meta property="og:image" content="https://telegram.org/img/t_logo_2x.png">'))) as client:
            self.assertIsNone(fetch_avatar('employee_one', client))

    def test_invalid_or_oversized_response_rejected(self):
        def handler(req):
            return httpx.Response(200, content=b'x' * 270000)
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(ValueError):
                fetch_avatar('employee_one', client)
        def handler(req):
            return httpx.Response(302, headers={'Location': 'http://127.0.0.1/private'})
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(httpx.HTTPStatusError):
                fetch_avatar('employee_one', client)

    def test_all_45_active_only_cached_no_staff_mutations(self):
        people = [SimpleNamespace(id=uuid4(), name=f'Employee {i:02}', status='active', fields={'F': f'@employee_{i:02}', 'N': 'Keep note'}) for i in range(45)]
        people.append(SimpleNamespace(id=uuid4(), name='Inactive', status='inactive', fields={'F': '@inactive'}))
        original = [dict(p.fields) for p in people]
        with tempfile.TemporaryDirectory() as root, patch('app.services.staff_avatars.fetch_avatar', return_value=(picture(), 'image/jpeg')) as fetch:
            result = sync_active(people, root)
            self.assertEqual(len(result), 45)
            self.assertEqual(fetch.call_count, 45)
            self.assertTrue(all(x['status'] == 'saved' for x in result))
            entry, path = avatar_entry(people[0], root)
            self.assertEqual(path.read_bytes(), picture())
            self.assertIsNone(avatar_entry(people[-1], root))
            self.assertEqual([p.fields for p in people], original)
            people[0].fields['F'] = '@changed_username'
            self.assertIsNone(avatar_entry(people[0], root), 'Never show a photo from an old username')
            index = json.loads((Path(root) / 'staff-avatars/index.json').read_text())
            index[str(people[1].id)]['sha256'] = '../../outside'
            (Path(root) / 'staff-avatars/index.json').write_text(json.dumps(index))
            self.assertIsNone(avatar_entry(people[1], root))
