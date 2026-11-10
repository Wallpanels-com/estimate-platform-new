"""Persist manually placed employee cards without changing reporting lines."""
from alembic import op
import sqlalchemy as sa

revision = '0015_staff_chart_positions'
down_revision = '0014_hr_translations'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('hr_staff_charts', sa.Column('positions', sa.JSON(), nullable=False, server_default='{}'))


def downgrade():
    op.drop_column('hr_staff_charts', 'positions')
