"""Editable candidate statuses and private candidate attachments. Existing HR records are retained."""
from alembic import op
import sqlalchemy as sa
revision='0013_hr_workflow_tools'
down_revision='0012_hr_staff_charts'
branch_labels=None
depends_on=None

def upgrade():
    status=op.create_table('hr_candidate_statuses',sa.Column('key',sa.String(30),primary_key=True),sa.Column('name_en',sa.String(120),nullable=False),sa.Column('name_ru',sa.String(120),nullable=False),sa.Column('position',sa.Integer(),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('deleted',sa.Boolean(),nullable=False))
    rows=[('new','New candidate','Новый кандидат'),('review','In review','На рассмотрении'),('contacted','Contacted','Связались'),('interview','Interview','Собеседование'),('offer','Offer','Предложение'),('hired','Hired','Нанят'),('rejected','Not selected','Не выбран'),('archived','Archived','В архиве')]
    op.bulk_insert(status,[dict(key=k,name_en=en,name_ru=ru,position=i,version=1,deleted=False) for i,(k,en,ru) in enumerate(rows)])
    op.create_table('hr_candidate_attachments',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('candidate_id',sa.Uuid(),sa.ForeignKey('hr_candidates.id'),nullable=False),sa.Column('name',sa.String(240),nullable=False),sa.Column('size',sa.Integer(),nullable=False),sa.Column('created_by',sa.String(240),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_hr_candidate_attachments_candidate_id','hr_candidate_attachments',['candidate_id'])

def downgrade():
    op.drop_table('hr_candidate_attachments')
    op.drop_table('hr_candidate_statuses')
