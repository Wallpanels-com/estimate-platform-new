"""One role, authenticated shared access and safe author metadata."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend"))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@localhost/unused")
os.environ.setdefault("SECRET_KEY", "test-only")
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from app.api import deps
from app.schemas.auth import UserCreate, UserUpdate
from app.api.v1 import estimates
from app.schemas.estimate import EstimateUpdate


class UniformAccess(unittest.IsolatedAsyncioTestCase):
    def test_only_user_role_can_be_created_or_assigned(self):
        values = dict(email="employee@example.com", name="Employee", password="long-test-password")
        self.assertEqual(UserCreate(**values).role, "user")
        for role in ("admin", "sales", "owner"):
            with self.assertRaises(ValidationError):
                UserCreate(**values, role=role)
            with self.assertRaises(ValidationError):
                UserUpdate(role=role)

    async def test_disabled_and_password_reset_sessions_are_rejected(self):
        ident = uuid.uuid4()
        for active, version, token_version, allowed in [(True, 2, 2, True), (False, 2, 2, False), (True, 3, 2, False)]:
            user = SimpleNamespace(id=ident, role="user", is_active=active, token_version=version, name="Employee", email="employee@example.com")
            db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: user)), info={})
            with patch.object(deps, "decode_token", return_value={"sub": str(ident), "ver": token_version}):
                if allowed:
                    self.assertIs(await deps.get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials="test"), db), user)
                    self.assertEqual(db.info["actor"]["name"], "Employee")
                else:
                    with self.assertRaises(HTTPException) as error:
                        await deps.get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials="test"), db)
                    self.assertEqual(error.exception.status_code, 401)

    async def test_prepared_by_cannot_be_spoofed_by_a_patch(self):
        estimate = SimpleNamespace(prepared_by="Original author", title="Title", type="pre")
        user = SimpleNamespace(name="Editor", email="editor@example.com")
        db = SimpleNamespace(flush=AsyncMock(), commit=AsyncMock())
        with patch.object(estimates, "load_estimate", new=AsyncMock(return_value=estimate)):
            await estimates.update_estimate(uuid.uuid4(), EstimateUpdate(prepared_by="Spoofed", title="Edited"), db, user)
        self.assertEqual(estimate.prepared_by, "Original author")
        self.assertEqual(estimate.updated_by_name, "Editor")


if __name__ == "__main__":
    unittest.main()
