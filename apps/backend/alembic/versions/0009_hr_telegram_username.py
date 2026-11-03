"""Store public Telegram handles supplied by HR; no Telegram session or lookup."""
from alembic import op
import sqlalchemy as sa
revision = '0009_hr_telegram_username'
down_revision = '0008_hr_candidate_visibility'

def upgrade():
    op.add_column('hr_candidates', sa.Column('telegram_username', sa.String(32), nullable=True))

def downgrade():
    op.drop_column('hr_candidates', 'telegram_username')
