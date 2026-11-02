"""Add isolated HR tables. Existing accounts do not receive HR access."""
from alembic import op
import sqlalchemy as sa
revision = '0007_hr_department'
down_revision = '0006_user_page_access'

def upgrade():
    op.create_table('hr_vacancies', sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('name',sa.String(160),nullable=False),sa.Column('description',sa.String(),nullable=False),sa.Column('archived',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_table('hr_candidates',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('vacancy_id',sa.Uuid(),sa.ForeignKey('hr_vacancies.id'),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('name',sa.String(240),nullable=False),sa.Column('email',sa.String(320),nullable=False),sa.Column('phone',sa.String(100),nullable=False),sa.Column('answers',sa.JSON(),nullable=False),sa.Column('source',sa.String(240),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('priority',sa.Boolean(),nullable=False),sa.Column('location',sa.String(240),nullable=False),sa.Column('location_verified',sa.Boolean(),nullable=False),sa.Column('score',sa.Integer(),nullable=True),sa.Column('notes',sa.String(),nullable=False),sa.Column('updated_by',sa.String(240),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint('vacancy_id','fingerprint',name='uq_hr_candidate_source'))
    op.create_index('ix_hr_candidates_vacancy_id','hr_candidates',['vacancy_id'])
    op.create_index('ix_hr_candidates_status','hr_candidates',['status'])
    op.create_table('hr_imports',sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('vacancy_id',sa.Uuid(),sa.ForeignKey('hr_vacancies.id'),nullable=False),sa.Column('filename',sa.String(240),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),sa.Column('result',sa.JSON(),nullable=True),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_hr_imports_vacancy_id','hr_imports',['vacancy_id'])

def downgrade():
    op.drop_table('hr_imports');op.drop_table('hr_candidates');op.drop_table('hr_vacancies')
