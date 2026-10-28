"""Retire category nesting and seed the requested mirror/furniture rates."""
from copy import deepcopy
from alembic import op
import sqlalchemy as sa
import uuid

revision='0005_flat_pricebook_rates'
down_revision='0004_employee_author_names'

def upgrade():
    conn=op.get_bind();conn.execute(sa.text('SELECT pg_advisory_xact_lock(782431650)'))
    row=conn.execute(sa.text('SELECT id,config FROM pricing_config LIMIT 1 FOR UPDATE')).mappings().first()
    if not row:return
    config=deepcopy(row['config']);original=deepcopy(config)
    types=config.setdefault('mirror',{}).setdefault('types',{})
    for key,label,ru,rate in [('rustic','Rustic Mirror','Деревенское зеркало',100),('bronze','Bronze Mirror','Бронзовое зеркало',100),('clear','Clear Mirror','Чистое зеркало',80)]:
        types.setdefault(key,{'label':label,'label_ru':ru,'rate':rate})
    config.setdefault('cabinet',{}).setdefault('types',{}).setdefault('shelving_unit',{'label':'Shelving Unit','label_ru':'Полочный шкаф','base_rate':800})
    book=config.get('_catalog_v1',{});categories=book.get('categories',[])
    lookup={c['id']:deepcopy(c) for c in categories}
    for category in categories:
        if not category.get('parent_id'):continue
        current=category;seen=set();archived=bool(current.get('archived'))
        while current.get('parent_id') in lookup and current['parent_id'] not in seen:
            seen.add(current['parent_id']);current=lookup[current['parent_id']];archived|=bool(current.get('archived'))
        category.update(parent_id=None,archived=archived,version=category.get('version',0)+1)
    if config==original:return
    pricing=sa.table('pricing_config',sa.column('id',sa.Uuid()),sa.column('config',sa.JSON()))
    conn.execute(pricing.update().where(pricing.c.id==row['id']).values(config=config))
    audit=sa.table('audit_events',sa.column('id',sa.Uuid()),sa.column('actor_name',sa.String()),sa.column('entity',sa.String()),sa.column('entity_id',sa.String()),sa.column('action',sa.String()),sa.column('changes',sa.JSON()))
    conn.execute(audit.insert().values(id=uuid.uuid4(),actor_name='Price Book structure update',entity='pricing_config',entity_id=str(row['id']),action='update',changes={'config':{'before':original,'after':config}}))

def downgrade():
    # Never discard subsequent staff price edits.
    pass
