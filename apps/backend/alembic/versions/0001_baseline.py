"""Freeze the pre-corporate schema; no customer data is included."""
from pathlib import Path
from alembic import op

revision = "0001_baseline"
down_revision = None


def upgrade():
    sql = (Path(__file__).resolve().parents[1] / "baseline.sql").read_text()
    for statement in sql.split("-- statement-split"):
        op.execute(statement.strip())


def downgrade():
    raise RuntimeError("Baseline downgrade would destroy data. Restore an approved backup into a separate database.")
