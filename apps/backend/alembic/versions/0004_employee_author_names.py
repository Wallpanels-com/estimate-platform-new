"""Refresh estimate author labels from employee identities and rename history.

Only attribution strings change. Prices, dates, branch overrides, files and
immutable historical records remain intact. No employee names are hard-coded.
"""
import uuid
from collections import defaultdict
from alembic import op
import sqlalchemy as sa

revision = '0004_employee_author_names'
down_revision = '0003_uniform_users'
FIELDS = ('prepared_by', 'created_by_name', 'updated_by_name')


def author_changes(users, history, estimates):
    users = {str(u['id']): u for u in users}
    aliases = defaultdict(set)
    def add(value, ident):
        if isinstance(value, str) and value.strip() and ident in users:
            aliases[value.strip().casefold()].add(ident)
    for ident, user in users.items():
        add(user['name'], ident)
        add(user['email'], ident)
    for event in history:
        ident = str(event['entity_id'])
        for field in ('name', 'email'):
            for side in ('before', 'after'):
                add((event['changes'].get(field) or {}).get(side), ident)
    for estimate in estimates:
        changes = {}
        owner = str(estimate['user_id'])
        for field in FIELDS:
            previous = estimate[field]
            candidates = aliases.get((previous or '').strip().casefold(), set())
            # Creator-linked fields can be resolved even if old names overlap.
            ident = owner if field != 'updated_by_name' and owner in candidates else next(iter(candidates)) if len(candidates) == 1 else None
            if not previous and field != 'updated_by_name' and owner in users:
                ident = owner
            name = (users[ident]['name'] or users[ident]['email']) if ident else None
            if name and name != previous:
                changes[field] = {'before': previous, 'after': name}
        if changes:
            yield estimate['id'], changes


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text('SELECT pg_advisory_xact_lock(18724301)'))
    users = connection.execute(sa.text('SELECT id,name,email FROM users')).mappings().all()
    history = connection.execute(sa.text("SELECT entity_id,changes FROM audit_events WHERE entity='users'")).mappings().all()
    # Match normal Pre-before-Final locking; metadata repair cannot overwrite edits.
    estimates = connection.execute(sa.text('SELECT id,user_id,prepared_by,created_by_name,updated_by_name FROM estimates ORDER BY (source_estimate_id IS NOT NULL),id FOR UPDATE')).mappings().all()
    audit = sa.table('audit_events', sa.column('id', sa.Uuid()), sa.column('actor_name',sa.String()),
                     sa.column('estimate_id',sa.Uuid()), sa.column('entity',sa.String()),
                     sa.column('entity_id',sa.String()), sa.column('action',sa.String()),sa.column('changes',sa.JSON()))
    for ident, changes in author_changes(users, history, estimates):
        # Whitelisted metadata columns only; raw SQL intentionally keeps updated_at.
        assignments = ','.join(f'{field}=:{field}' for field in changes)
        connection.execute(sa.text(f'UPDATE estimates SET {assignments} WHERE id=:id'),
                           {'id':ident, **{field:detail['after'] for field,detail in changes.items()}})
        connection.execute(audit.insert().values(id=uuid.uuid4(), actor_name='Employee author-name correction',
            estimate_id=ident,entity='estimates',entity_id=str(ident),action='author_names_updated',changes=changes))


def downgrade():
    # Do not restore obsolete names or overwrite later employee edits.
    pass
