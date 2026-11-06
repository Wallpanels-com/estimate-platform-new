"""Private staff directory, source data and editable reporting lines."""
from alembic import op
import sqlalchemy as sa
revision = '0011_hr_staff'
down_revision = '0010_hr_ai_reviews'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('hr_staff',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('source_key', sa.String(64), unique=True, nullable=False),
        sa.Column('source', sa.JSON(), nullable=False),
        sa.Column('name', sa.String(240), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('title', sa.String(240), nullable=False),
        sa.Column('department', sa.String(160), nullable=False),
        sa.Column('fields', sa.JSON(), nullable=False),
        sa.Column('links', sa.JSON(), nullable=False),
        sa.Column('manager_id', sa.Uuid(), sa.ForeignKey('hr_staff.id'), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('updated_by', sa.String(240), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index('ix_hr_staff_manager_id', 'hr_staff', ['manager_id'])


def downgrade():
    op.drop_table('hr_staff')
