import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend"))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost/db")
os.environ.setdefault("SECRET_KEY", "unit-tests-only")

from app.core.config import Settings


class SettingsTests(unittest.TestCase):
    def test_standard_provider_postgres_url_uses_async_driver(self):
        settings = Settings(
            DATABASE_URL="postgresql://user:pass@host.example/database",
            SECRET_KEY="test-only",
        )
        self.assertEqual(
            settings.DATABASE_URL,
            "postgresql+asyncpg://user:pass@host.example/database",
        )

    def test_explicit_async_driver_is_unchanged(self):
        url = "postgresql+asyncpg://user:pass@localhost/database"
        settings = Settings(DATABASE_URL=url, SECRET_KEY="test-only")
        self.assertEqual(settings.DATABASE_URL, url)


if __name__ == "__main__":
    unittest.main()
