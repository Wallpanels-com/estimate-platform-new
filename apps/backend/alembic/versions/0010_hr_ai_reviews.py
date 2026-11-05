"""Persist on-demand HR AI reviews separately from candidate records."""
from alembic import op
import sqlalchemy as sa
revision='0010_hr_ai_reviews'
down_revision='0009_hr_telegram_username'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('hr_ai_reviews',
        sa.Column('candidate_id',sa.Uuid(),sa.ForeignKey('hr_candidates.id'),primary_key=True),
        sa.Column('source_hash',sa.String(64),nullable=False),
        sa.Column('content',sa.JSON(),nullable=False),
        sa.Column('message_draft',sa.Text(),nullable=False),
        sa.Column('model',sa.String(100),nullable=False),
        sa.Column('created_by',sa.String(240),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
def downgrade():
    op.drop_table('hr_ai_reviews')
