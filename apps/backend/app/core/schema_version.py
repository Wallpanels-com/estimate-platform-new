"""Resolve the release's expected database revision from its migration files."""
from pathlib import Path
from alembic.script import ScriptDirectory


def current_revision():
    return ScriptDirectory(str(Path(__file__).resolve().parents[2] / 'alembic')).get_current_head()
