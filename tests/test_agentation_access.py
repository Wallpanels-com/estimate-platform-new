"""Agentation is granted only by the configured immutable user ID."""
import os,sys,unittest,uuid
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/backend'))
os.environ.setdefault('DATABASE_URL','postgresql+asyncpg://unused:unused@127.0.0.1:55432/unused')
os.environ.setdefault('SECRET_KEY','unit-tests-only')
from app.api.v1.auth import user_profile, settings

class AgentationAccess(unittest.TestCase):
    def test_only_the_active_configured_identity_can_use_toolbar(self):
        owner=uuid.uuid4()
        def user(ident,login='dmitry',active=True):
            return SimpleNamespace(id=ident,email=login,name='Dmitry',role='user',is_active=active,onboarding_completed=True,created_at=datetime.now(timezone.utc))
        with patch.object(settings,'AGENTATION_USER_ID',owner):
            self.assertTrue(user_profile(user(owner,'renamed.login')).agentation_enabled)
            self.assertFalse(user_profile(user(uuid.uuid4())).agentation_enabled)
            self.assertFalse(user_profile(user(owner,active=False)).agentation_enabled)
        with patch.object(settings,'AGENTATION_USER_ID',None):
            self.assertFalse(user_profile(user(owner)).agentation_enabled)
