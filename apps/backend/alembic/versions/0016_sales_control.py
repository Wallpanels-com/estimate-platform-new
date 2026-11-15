"""Owner-only Sales Control mirror; existing business and user data untouched."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '0016_sales_control'
down_revision = '0015_staff_chart_positions'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sales_records',
        sa.Column('location_id', sa.String(64), primary_key=True),
        sa.Column('kind', sa.String(32), primary_key=True),
        sa.Column('external_id', sa.String(128), primary_key=True),
        sa.Column('contact_id', sa.String(64)), sa.Column('parent_id', sa.String(128)),
        sa.Column('occurred_at', sa.DateTime(timezone=True)),
        sa.Column('seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('payload', JSONB(), nullable=False))
    for name, cols in [('ix_sales_kind_date',['location_id','kind','occurred_at']),('ix_sales_contact',['location_id','contact_id','kind']),('ix_sales_parent',['location_id','kind','parent_id'])]:
        op.create_index(name,'sales_records',cols)
    op.create_table('sales_sync',
        sa.Column('location_id',sa.String(64),primary_key=True),sa.Column('resource',sa.String(64),primary_key=True),
        sa.Column('state',JSONB(),nullable=False),sa.Column('last_success',sa.DateTime(timezone=True)),
        sa.Column('next_run',sa.DateTime(timezone=True),nullable=False),sa.Column('error',sa.Text()))
    op.create_table('sales_jobs',
        sa.Column('location_id',sa.String(64),primary_key=True),sa.Column('key',sa.String(180),primary_key=True),
        sa.Column('kind',sa.String(32),nullable=False),sa.Column('payload',JSONB(),nullable=False),
        sa.Column('priority',sa.Integer(),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False),
        sa.Column('next_run',sa.DateTime(timezone=True),nullable=False),sa.Column('error',sa.Text()))
    op.create_index('ix_sales_jobs_next_run','sales_jobs',['next_run'])
    op.create_table('sales_analyses',
        sa.Column('location_id',sa.String(64),primary_key=True),sa.Column('source_id',sa.String(160),primary_key=True),
        sa.Column('contact_id',sa.String(64)),sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.Column('model',sa.String(100),nullable=False),sa.Column('payload',JSONB(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_sales_analyses_contact_id','sales_analyses',['contact_id'])
    op.create_index('ix_sales_analyses_created_at','sales_analyses',['created_at'])


def downgrade():
    for name in ['sales_analyses','sales_jobs','sales_sync','sales_records']:
        op.drop_table(name)
