"""Persist private org-chart collaboration links and aligned card order."""
from alembic import op
import sqlalchemy as sa
revision = '0012_hr_staff_charts'
down_revision = '0011_hr_staff'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('hr_staff_charts',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('name', sa.String(40), unique=True, nullable=False),
        sa.Column('extra_edges', sa.JSON(), nullable=False),
        sa.Column('orders', sa.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.String(240), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade():
    op.drop_table('hr_staff_charts')
