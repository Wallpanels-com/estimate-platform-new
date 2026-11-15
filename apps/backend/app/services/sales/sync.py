"""Resumable polling with a PostgreSQL leader lock and durable cursors/jobs."""
import asyncio
import logging
from datetime import timedelta
from sqlalchemy import select, update, text, func
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.sales import SalesSync, SalesJob, SalesRecord
from .client import GhlClient, GhlError
from .store import now, loc, stamp, save, enqueue, get_record, digest

log=logging.getLogger(__name__)
RESOURCES=('users','pipelines','numbers','agents','voice','opportunity_changes','opportunities','recent','history','fields')

async def state_for(db,resource):
    row=await db.get(SalesSync,(loc(),resource))
    if row is None:
        row=SalesSync(location_id=loc(),resource=resource,state={},next_run=now())
        db.add(row);await db.flush()
    return row

async def reconcile(db,kind,items,start):
    for item in items: await save(db,kind,item)
    # Only retire absent records after a successful COMPLETE list, never on an error.
    await db.execute(update(SalesRecord).where(SalesRecord.location_id==loc(),SalesRecord.kind==kind,SalesRecord.seen_at<start).values(active=False))

async def save_opportunity(db,item):
    old=await get_record(db,'opportunities',item['id'])
    previous=stamp(old.payload.get('updatedAt')) if old else None
    incoming=stamp(item.get('updatedAt'))
    if previous and incoming and previous>incoming:return
    if old and any(old.payload.get(k)!=item.get(k) for k in ('pipelineStageId','status','assignedTo')):
        event={'id':item['id']+'-'+digest({k:item.get(k) for k in ('updatedAt','pipelineStageId','status','assignedTo')})[:16],
            'contactId':item.get('contactId'),'opportunityId':item['id'],'name':item.get('name'),
            'before':{k:old.payload.get(k) for k in ('pipelineStageId','status','assignedTo')},
            'after':{k:item.get(k) for k in ('pipelineStageId','status','assignedTo')},'dateAdded':now().isoformat()}
        await save(db,'stage_events',event)
    for note in item.get('notes') or []:
        if isinstance(note,dict):await save(db,'notes',{**note,'contactId':item.get('contactId')})
    await save(db,'opportunities',item)

async def sync_resource(db,c,resource):
    row=await state_for(db,resource)
    if row.next_run>now(): return
    state=dict(row.state); started=now(); delay=60
    if resource in ('users','pipelines','fields'):
        path={'users':'/users/','pipelines':'/opportunities/pipelines','fields':f'/locations/{loc()}/customFields'}[resource]
        data=await c.get(path,{'locationId':loc()} if resource!='fields' else None)
        key={'users':'users','pipelines':'pipelines','fields':'customFields'}[resource]
        await reconcile(db,resource,data[key],started)
        state={'count':len(data[key]),'complete':True};delay=60 if resource=='users' else 600
    elif resource=='numbers':
        items=[]
        for page in range(100):
            data=await c.get(f'/phone-system/numbers/location/{loc()}',{'pageSize':100,'page':page,'skipNumberPool':'false'})
            data=data.get('data',data);batch=data['numbers'];items.extend(batch)
            if len(batch)<100:break
        else: raise ValueError('Number pagination did not finish')
        await reconcile(db,'numbers',items,started)
        state={'count':len(items),'complete':True}
    elif resource=='agents':
        items=[]
        for page in range(1,101):
            d=await c.get('/voice-ai/agents',{'locationId':loc(),'page':page,'pageSize':50});items.extend(d['agents'])
            if len(items)>=d.get('total',len(items)) or not d['agents']:break
        else:raise ValueError('Agent pagination did not finish')
        # Keep instructions for evidence, exclude action credentials via clean_payload.
        await reconcile(db,'agents',items,started)
        state={'count':len(items),'complete':True};delay=600
    elif resource=='opportunity_changes':
        if not state.get('until'):
            state={'since':state.get('checkpoint') or (started-timedelta(days=1)).isoformat(),
                'until':started.isoformat(),'loaded':0}
        d=await c.search_changed_opportunities(state['since'],state['until'],state.get('cursor'))
        items=d['opportunities']
        for item in items:await save_opportunity(db,item)
        state['loaded']+=len(items);state['total']=d.get('total')
        if len(items)==100:
            cursor=items[-1].get('sort')
            if not cursor or cursor==state.get('cursor'):raise ValueError('Repeated change cursor')
            state['cursor']=cursor;delay=0
        else:
            # Replay a five-minute overlap to tolerate indexing delay.
            state={'checkpoint':(stamp(state['until'])-timedelta(minutes=5)).isoformat(),'complete':True,
                'loaded':state['loaded'],'total':state['total']};delay=60
    elif resource=='opportunities':
        params={'location_id':loc(),'limit':100,'order':'added_desc','status':'all','getNotes':'true'}
        if state.get('cursor'):params.update(state['cursor'])
        else:state={'scan_started':started.isoformat(),'loaded':0,'completed_at':state.get('completed_at')}
        d=await c.get('/opportunities/search',params)
        for item in d['opportunities']:
            await save_opportunity(db,item)
        meta=d['meta']; state['total']=meta.get('total');state['loaded']+=len(d['opportunities'])
        if d['opportunities'] and meta.get('nextPage') and meta.get('startAfterId'):
            cursor={'startAfter':meta['startAfter'],'startAfterId':meta['startAfterId']}
            if cursor==state.get('cursor'):raise ValueError('Repeated opportunity cursor')
            state['cursor']=cursor;delay=0
        else:
            await db.execute(update(SalesRecord).where(SalesRecord.location_id==loc(),SalesRecord.kind=='opportunities',SalesRecord.seen_at<stamp(state['scan_started'])).values(active=False))
            state.update(cursor=None,complete=True,completed_at=started.isoformat());delay=300
    elif resource=='voice':
        params={'locationId':loc(),'pageSize':50,'page':state.get('page',1)}
        d=await c.get('/voice-ai/dashboard/call-logs',params)
        cutoff=now()-timedelta(days=settings.SALES_HISTORY_DAYS)
        for item in d['callLogs']:
            await save(db,'calls',item)
            if item.get('transcript') and not item.get('trialCall') and (stamp(item.get('createdAt')) or now())>=cutoff:
                await enqueue(db,'analysis','call:'+item['id'],{'source_kind':'calls','id':item['id']},priority=10)
        if d['callLogs'] and params['page']*50<d['total']:
            state={'page':params['page']+1,'total':d['total']};delay=0
        else:state={'page':1,'total':d['total'],'complete':True};delay=60
    elif resource in ('recent','history'):
        if resource=='history' and state.get('complete'): row.next_run=started+timedelta(days=1);return
        params={'locationId':loc(),'limit':100,'sort':'desc','sortBy':'last_message_date'}
        if state.get('cursor') is not None:params['startAfterDate']=state['cursor']
        d=await c.get('/conversations/search',params);items=d['conversations']
        cutoff=now()-timedelta(days=settings.SALES_HISTORY_DAYS)
        first_recent = resource=='recent' and not state.get('initialized')
        unchanged=0
        for item in items:
            old=await get_record(db,'conversations',item['id'])
            old_stamp=(old.payload.get('lastMessageDate'),old.payload.get('lastMessageBody')) if old else None
            if old_stamp==(item.get('lastMessageDate'),item.get('lastMessageBody')):unchanged+=1
            elif (stamp(item.get('lastMessageDate')) or now())>=cutoff:
                await enqueue(db,'messages',item['id'],{'id':item['id'],'contactId':item['contactId']},priority=5 if resource=='recent' else 0)
            await save(db,'conversations',item)
        state['total']=d.get('total');state['loaded']=state.get('loaded',0)+len(items)
        last=items[-1] if items else {}
        sort=last.get('sort');cursor=sort[0] if isinstance(sort,list) and sort else last.get('lastMessageDate')
        ended=not items or len(items)<100 or (stamp(last.get('lastMessageDate')) or cutoff)<cutoff
        if resource=='recent' and (unchanged==len(items) or first_recent):ended=True
        if ended:
            state.update(cursor=None,complete=True,initialized=True);delay=60 if resource=='recent' else 86400
        elif cursor is None or cursor==state.get('cursor'):
            raise ValueError('Conversation pagination needs reconciliation')
        else:state['cursor']=cursor;delay=0
    row.state=state;row.last_success=now();row.error=None;row.next_run=now()+timedelta(seconds=delay)

async def sync_messages(db,c,job):
    p=dict(job.payload);params={'limit':100}
    if p.get('cursor'):params['lastMessageId']=p['cursor']
    d=(await c.get('/conversations/'+p['id']+'/messages',params))['messages'];items=d['messages']
    cutoff=now()-timedelta(days=settings.SALES_HISTORY_DAYS)
    for item in items:
        await save(db,'messages',item,parent=p['id'])
        if item.get('messageType')=='TYPE_CALL' and item.get('status') in ('completed','connected') and (stamp(item.get('dateAdded')) or now())>=cutoff:
            trans=await get_record(db,'transcripts',item['id'])
            if not trans or not trans.payload.get('segments'):
                await enqueue(db,'transcript',item['id'],{'id':item['id'],'contactId':p.get('contactId')})
    if items and d.get('nextPage') and (stamp(items[-1].get('dateAdded')) or now())>=cutoff:
        cursor=d.get('lastMessageId')
        if not cursor or cursor==p.get('cursor'):raise ValueError('Repeated message cursor')
        p['cursor']=cursor;job.payload=p;job.next_run=now();return False
    await enqueue(db,'contact',p['contactId'],priority=job.priority)
    await enqueue(db,'analysis','conversation:'+p['id'],{'source_kind':'messages','id':p['id'],'contactId':p['contactId']},priority=job.priority)
    sync=await state_for(db,'messages:'+p['id']);sync.last_success=now();sync.state={'complete':True,'history_days':settings.SALES_HISTORY_DAYS};sync.next_run=now()+timedelta(seconds=60);sync.error=None
    return True

async def sync_contact(db,c,job):
    cid=job.payload['id']; d=await c.get('/contacts/'+cid)
    await save(db,'contacts',d['contact'])
    warnings=[]
    for kind in ('notes','tasks'):
        try:
            started=now()
            d=await c.get('/contacts/'+cid+'/'+kind)
            for item in d[kind]:await save(db,kind,{**item,'contactId':cid})
            await db.execute(update(SalesRecord).where(SalesRecord.location_id==loc(),SalesRecord.kind==kind,SalesRecord.contact_id==cid,SalesRecord.seen_at<started).values(active=False))
        except GhlError as e: warnings.append(f'{kind}: {e}')
    s=await state_for(db,'contact:'+cid);s.last_success=now();s.state={'complete':True};s.error='; '.join(warnings) or None;s.next_run=now()+timedelta(minutes=5)
    return True

async def sync_transcript(db,c,job):
    p=job.payload
    try:
        data=await c.get(f'/conversations/locations/{loc()}/messages/{p["id"]}/transcription')
    except GhlError as e:
        if e.status in (400,404):
            await save(db,'transcripts',{'id':p['id'],'contactId':p.get('contactId'),'segments':[],'availability':'not_available'})
            if job.attempts>=5:return True
        raise
    segments=data if isinstance(data,list) else data.get('transcriptions',data.get('transcription',data.get('data',[])))
    if not isinstance(segments,list):raise ValueError('Unsupported transcript shape')
    await save(db,'transcripts',{'id':p['id'],'contactId':p.get('contactId'),'segments':segments,'availability':'available'})
    await enqueue(db,'analysis','transcript:'+p['id'],{'source_kind':'transcripts','id':p['id'],'contactId':p.get('contactId')},priority=2)
    return True

async def process_job(db,c,job):
    if job.kind=='discover':
        cid=job.payload['id']
        data=await c.get('/conversations/search',{'locationId':loc(),'contactId':cid,'limit':100})
        for item in data['conversations']:
            await save(db,'conversations',item)
            await enqueue(db,'messages',item['id'],{'id':item['id'],'contactId':cid},priority=50)
        return True
    if job.kind=='messages':return await sync_messages(db,c,job)
    if job.kind=='contact':return await sync_contact(db,c,job)
    if job.kind=='transcript':return await sync_transcript(db,c,job)
    if job.kind=='analysis':
        from .analysis import analyze
        return await analyze(db,job)
    raise ValueError('Unknown job')

async def poll_resources(c):
    for name in RESOURCES:
        async with AsyncSessionLocal() as db:
            try:
                await sync_resource(db,c,name);await db.commit()
            except Exception as e:
                await db.rollback();row=await state_for(db,name)
                row.error=str(e) if isinstance(e,GhlError) else 'Sync interrupted; retry scheduled.'
                row.next_run=now()+timedelta(seconds=60 if not isinstance(e,GhlError) or e.status!=429 else 120)
                await db.commit()

async def poll_jobs(c, analysis_only=False):
    # Priority work first; preserve durable job state across restarts and failures.
    for _ in range(1 if analysis_only else 12):
        async with AsyncSessionLocal() as db:
            job=await db.scalar(select(SalesJob).where(SalesJob.location_id==loc(),SalesJob.next_run<=now(),SalesJob.kind=='analysis' if analysis_only else SalesJob.kind!='analysis').order_by(SalesJob.priority.desc(),SalesJob.next_run).limit(1).with_for_update(skip_locked=True))
            if not job:break
            key=job.key
            try:
                done=await process_job(db,c,job)
                if done:await db.delete(job)
                await db.commit()
            except Exception as e:
                await db.rollback();job=await db.get(SalesJob,(loc(),key))
                job.attempts+=1
                job.error=str(e) if isinstance(e,GhlError) else 'Processing unavailable; retry scheduled.'
                job.next_run=now()+timedelta(seconds=min(86400,120*2**min(job.attempts,9)))
                await db.commit()

async def poll_analysis(c):
    await poll_jobs(c, analysis_only=True)

async def run_worker():
    if not (settings.SALES_SYNC_ENABLED and settings.SALES_GHL_TOKEN and loc()):return
    while True:
        try:
            async with engine.connect() as lock:
                acquired=await lock.scalar(text('SELECT pg_try_advisory_lock(731940116)'))
                await lock.commit()
                if not acquired:
                    await asyncio.sleep(10);continue
                c=GhlClient()
                try:
                    async def poll_loop(fn):
                        while True:
                            await fn(c)
                            await asyncio.sleep(2)
                    async with asyncio.TaskGroup() as group:
                        group.create_task(poll_loop(poll_resources))
                        group.create_task(poll_loop(poll_jobs))
                        group.create_task(poll_loop(poll_analysis))
                finally:
                    await c.close()
                    await lock.execute(text('SELECT pg_advisory_unlock(731940116)'));await lock.commit()
        except asyncio.CancelledError:raise
        except Exception:
            log.warning('Sales worker interrupted; restarting without modifying CRM.')
            await asyncio.sleep(15)

if __name__=='__main__':asyncio.run(run_worker())
