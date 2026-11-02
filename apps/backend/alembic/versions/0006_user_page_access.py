"""Add optional per-employee page grants without changing existing access."""
from alembic import op
import sqlalchemy as sa

revision = '0006_user_page_access'
down_revision = '0005_flat_pricebook_rates'


def upgrade():
    op.add_column('users', sa.Column('page_access', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('users', 'page_access')
