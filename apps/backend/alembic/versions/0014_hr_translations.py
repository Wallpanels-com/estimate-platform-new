"""Persistent display translations, independent of original HR records."""
from alembic import op
import sqlalchemy as sa

revision = '0014_hr_translations'
down_revision = '0013_hr_workflow_tools'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('hr_translations',
        sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('translated', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    op.drop_table('hr_translations')
