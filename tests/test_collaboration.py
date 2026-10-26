"""Login and concurrency contracts independent of deployment credentials."""
import os
from pathlib import Path
import sys
import unittest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/backend"))
os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@localhost/unused")
os.environ.setdefault("SECRET_KEY", "unit-tests-only")
from app.models.estimate import Estimate
from app.schemas.auth import LoginRequest, UserCreate


class CollaborationContracts(unittest.TestCase):
    def test_username_login_and_old_email_remain_supported(self):
        for login in ("dmitry", "katya1", "katya2", "employee@example.com"):
            self.assertEqual(LoginRequest(email=login.upper(), password="unused").email, login)
            self.assertEqual(UserCreate(email=login, name="Employee", password="temporary-password").role, "user")
        with self.assertRaises(ValueError):
            LoginRequest(email="invalid login", password="unused")

    def test_revision_tracks_both_saved_branch_and_source(self):
        now = datetime.now(timezone.utc)
        est = Estimate(id=uuid4(), updated_at=now)
        initial = est.revision
        self.assertEqual(initial, est.revision)
        est.updated_at = now + timedelta(microseconds=1)
        self.assertNotEqual(initial, est.revision)
        edited = est.revision
        est._source_revision = now
        self.assertNotEqual(edited, est.revision)
