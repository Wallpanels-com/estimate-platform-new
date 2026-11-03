import sys
from pathlib import Path
from unittest import TestCase
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/backend'))
from app.services.telegram_contacts import normalize_username

class TelegramHandles(TestCase):
    def test_public_handles_and_known_links(self):
        for value in ['example_user','@example_user',' https://t.me/example_user/ ','t.me/example_user','https://telegram.me/example_user']:
            self.assertEqual(normalize_username(value),'example_user')
        for value in [None,'','  ']:self.assertIsNone(normalize_username(value))
    def test_phone_numbers_paths_and_external_hosts_are_not_profiles(self):
        for value in ['380000000000','javascript:alert(1)','https://evil.example/example_user','https://t.me/example_user/42','https://t.me/example_user?text=hello','https://t.me/+380000000000','https://t.me/login','@@example_user','ab','x'*33]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):normalize_username(value)
