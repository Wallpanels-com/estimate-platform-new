"""Keep candidate visibility separate from hiring stage and priority."""
from alembic import op
import sqlalchemy as sa
revision = '0008_hr_candidate_visibility'
down_revision = '0007_hr_department'

def upgrade():
    op.add_column('hr_candidates', sa.Column('hidden', sa.Boolean(), server_default=sa.false(), nullable=False))

def downgrade():
    op.drop_column('hr_candidates', 'hidden')
