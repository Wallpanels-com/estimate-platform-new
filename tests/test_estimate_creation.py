"""Account author attribution and preservation of hidden estimate metadata."""
import uuid
import os
import sys
from pathlib import Path
from types import SimpleNamespace as Object
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/backend'))
os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://unused:unused@127.0.0.1:55432/unused')
os.environ.setdefault('SECRET_KEY', 'unit-tests-only')
from app.api.v1 import estimates
from app.schemas.estimate import EstimateCreate, EstimateUpdate


class EstimateCreation(IsolatedAsyncioTestCase):
    async def test_create_uses_account_author_and_preserves_initial_zone_rules(self):
        for kind in ('pre', 'final', 'quick'):
            for name in ('Sales person', None):
                with self.subTest(kind=kind, name=name):
                    user = Object(id=uuid.uuid4(), name=name, email='sales@local.test')
                    db = Object(add=Mock(), flush=AsyncMock(), commit=AsyncMock())
                    with patch.object(estimates, 'load_estimate', new=AsyncMock()) as load:
                        await estimates.create_estimate(
                            EstimateCreate(type=kind, client_name='Local QA', prepared_by='Typed override'),
                            db, user,
                        )
                    saved = db.add.call_args_list[0].args[0]
                    expected = name or user.email
                    self.assertEqual(saved.prepared_by, expected)
                    self.assertEqual(saved.created_by_name, expected)
                    self.assertEqual(saved.user_id, user.id)
                    self.assertEqual(saved.type, kind)
                    self.assertEqual(db.add.call_count, 1 if kind == 'quick' else 2)
                    db.commit.assert_awaited_once()
                    load.assert_awaited_once()

    async def test_details_update_preserves_omitted_notes_description_author_and_type(self):
        saved = Object(title='Old title', description='Existing description', notes='Existing notes',
                       prepared_by='Original sales person', type='final')
        db = Object(flush=AsyncMock(), commit=AsyncMock())
        user = Object(name='Current editor', email='editor@local.test')
        with patch.object(estimates, 'load_estimate', new=AsyncMock(return_value=saved)):
            await estimates.update_estimate(uuid.uuid4(), EstimateUpdate(title='New title'), db, user)
        self.assertEqual(saved.title, 'New title')
        self.assertEqual(saved.description, 'Existing description')
        self.assertEqual(saved.notes, 'Existing notes')
        self.assertEqual(saved.prepared_by, 'Original sales person')
        self.assertEqual(saved.type, 'final')
