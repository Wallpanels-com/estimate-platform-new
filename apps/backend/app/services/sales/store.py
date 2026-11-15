from datetime import datetime, timezone
import hashlib
import json
from sqlalchemy import select, case, func
from sqlalchemy.dialects.postgresql import insert
from app.models.sales import SalesRecord, SalesJob
from app.core.config import settings


def now(): return datetime.now(timezone.utc)
def loc(): return settings.SALES_GHL_LOCATION_ID

def stamp(value):
    try:
        if isinstance(value,(int,float)) or (isinstance(value,str) and value.isdigit()):
            n=float(value); return datetime.fromtimestamp(n/1000 if n>100000000000 else n,timezone.utc)
        if isinstance(value,str):
            parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError,TypeError,OverflowError,OSError): pass
    return None

def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()

def clean_payload(value):
    # Never persist credential-bearing tool/action configuration from Voice AI.
    blocked={'authenticationValue','headers','apiKey','password','token','secret','accessToken','refreshToken','scopes','scopesAssignedToOnly','permissions'}
    if isinstance(value,dict): return {k:clean_payload(v) for k,v in value.items() if k not in blocked}
    if isinstance(value,list): return [clean_payload(v) for v in value]
    return value

async def save(db,kind,payload,ident=None,parent=None,occurred=None):
    payload=clean_payload(payload)
    ident=str(ident or payload.get('id') or payload.get('_id') or payload.get('sid') or payload.get('phoneNumber') or '')
    if not ident: raise ValueError('Missing upstream identity')
    if payload.get('locationId') and payload['locationId']!=loc(): raise ValueError('Wrong GHL location')
    when=now()
    values=dict(location_id=loc(),kind=kind,external_id=ident,contact_id=payload.get('contactId'),parent_id=parent,
        occurred_at=stamp(occurred or payload.get('lastMessageDate') or payload.get('dateAdded') or payload.get('createdAt')),
        seen_at=when,changed_at=when,active=True,payload=payload)
    stmt=insert(SalesRecord).values(**values)
    update={k:getattr(stmt.excluded,k) for k in values if k not in ('location_id','kind','external_id','changed_at')}
    update['changed_at']=case((SalesRecord.payload!=stmt.excluded.payload,when),else_=SalesRecord.changed_at)
    await db.execute(stmt.on_conflict_do_update(index_elements=['location_id','kind','external_id'],set_=update))
    return ident

async def get_record(db,kind,ident):
    return await db.get(SalesRecord,(loc(),kind,ident))

async def enqueue(db,kind,ident,payload=None,priority=0):
    stmt=insert(SalesJob).values(location_id=loc(),key=f'{kind}:{ident}',kind=kind,payload=payload or {'id':ident},priority=priority,attempts=0,next_run=now())
    await db.execute(stmt.on_conflict_do_update(index_elements=['location_id','key'],set_={
        'priority':func.greatest(SalesJob.priority,priority),
        'next_run':case((SalesJob.priority<priority,now()),else_=SalesJob.next_run)}))

async def records(db,kind):
    return list((await db.scalars(select(SalesRecord).where(SalesRecord.location_id==loc(),SalesRecord.kind==kind,SalesRecord.active==True))).all())
