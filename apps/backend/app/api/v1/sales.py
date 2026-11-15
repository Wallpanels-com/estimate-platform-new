"""Owner-only read endpoints. Never sends a mutation to GoHighLevel."""
import csv
import io
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.config import settings
from app.models.sales import SalesRecord as R, SalesSync, SalesJob, SalesAnalysis
from app.services.sales.store import now, loc, enqueue, records, get_record
from app.services.sales.client import GhlClient, GhlError

router=APIRouter(prefix='/sales',tags=['Sales Control'],dependencies=[Depends(get_current_user)])


def base(kind): return select(R).where(R.location_id==loc(),R.kind==kind,R.active==True)
def serial(row): return {**row.payload,'_id':row.external_id,'_synced_at':row.seen_at,'_changed_at':row.changed_at,'_active':row.active}

def conditions(q='',pipeline='',stage='',owner='',status='',source='',from_date=None,to_date=None):
    result=[];p=R.payload
    if q:
        term='%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        result.append(or_(p['name'].astext.ilike(term),p['contact']['name'].astext.ilike(term),p['contact']['email'].astext.ilike(term),p['contact']['phone'].astext.ilike(term)))
    for key,value in [('pipelineId',pipeline),('pipelineStageId',stage),('assignedTo',owner),('source',source)]:
        if value: result.append(p[key].astext==value)
    if status=='review':result.append(p['status'].astext.in_(['lost','abandoned']))
    elif status:result.append(p['status'].astext==status)
    if from_date:result.append(R.occurred_at>=datetime.combine(from_date,datetime.min.time(),tzinfo=timezone.utc))
    if to_date:result.append(R.occurred_at<datetime.combine(to_date+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc))
    return result

def filters(q:str=Query('',max_length=200),pipeline:str='',stage:str='',owner:str='',status:str='',source:str='',from_date:date|None=None,to_date:date|None=None):
    if from_date and to_date and from_date>to_date:raise HTTPException(422,'Start date must precede end date.')
    return dict(q=q,pipeline=pipeline,stage=stage,owner=owner,status=status,source=source,from_date=from_date,to_date=to_date)

@router.get('/status')
async def status(db:AsyncSession=Depends(get_db)):
    states=(await db.scalars(select(SalesSync).where(SalesSync.location_id==loc(),~SalesSync.resource.like('contact:%'),~SalesSync.resource.like('messages:%')))).all()
    counts=dict((await db.execute(select(R.kind,func.count()).where(R.location_id==loc(),R.active==True).group_by(R.kind))).all())
    jobs=(await db.execute(select(SalesJob.kind,func.count()).where(SalesJob.location_id==loc()).group_by(SalesJob.kind))).all()
    errors=(await db.execute(select(SalesJob.kind,SalesJob.error,func.count()).where(SalesJob.location_id==loc(),SalesJob.error.is_not(None)).group_by(SalesJob.kind,SalesJob.error))).all()
    analyses=await db.scalar(select(func.count()).select_from(SalesAnalysis).where(SalesAnalysis.location_id==loc()))
    concerns=await db.scalar(select(func.count()).select_from(SalesAnalysis).where(SalesAnalysis.location_id==loc(),SalesAnalysis.payload['outcome'].astext=='review_needed'))
    return {'configured':bool(settings.SALES_GHL_TOKEN and loc()),'enabled':settings.SALES_SYNC_ENABLED,'read_only':True,'owner_only':True,'location_id':loc(),
        'counts':counts,'analyses':analyses,'concerns':concerns,'jobs':dict(jobs),'job_errors':[{'kind':k,'error':e,'count':n} for k,e,n in errors],
        'resources':[{'name':s.resource,'last_success':s.last_success,'next_run':s.next_run,'error':s.error,'state':s.state} for s in states],
        'history_days':settings.SALES_HISTORY_DAYS,'ai_daily_limit':settings.SALES_AI_DAILY_LIMIT,'policy_status':'no_approved_sales_ops'}

@router.get('/lookups')
async def lookups(db:AsyncSession=Depends(get_db)):
    return {'users':[{'id':r.external_id,'name':r.payload.get('name') or r.external_id,'deleted':r.payload.get('deleted',False)} for r in await records(db,'users')],
        'pipelines':[serial(r) for r in await records(db,'pipelines')],
        'agents':[{'id':r.external_id,'name':r.payload.get('agentName')} for r in await records(db,'agents')]}

@router.get('/opportunities')
async def opportunities(f:dict=Depends(filters),page:int=Query(1,ge=1),limit:int=Query(50,ge=1,le=100),db:AsyncSession=Depends(get_db)):
    query=base('opportunities').where(*conditions(**f))
    total=await db.scalar(select(func.count()).select_from(query.subquery()))
    items=(await db.scalars(query.order_by(R.occurred_at.desc().nullslast(),R.external_id).offset((page-1)*limit).limit(limit))).all()
    # One batched query: preserve the employee's wording and author, never infer
    # that a note is the reason a deal was lost.
    comments={}
    if f.get('status')=='review' and items:
        ids=[r.contact_id for r in items if r.contact_id]
        rows=(await db.scalars(select(R).where(R.location_id==loc(),R.active==True,R.contact_id.in_(ids),
            or_(R.kind=='notes',(R.kind=='messages') & R.payload['messageType'].astext.ilike('%INTERNAL%')))
            .distinct(R.contact_id).order_by(R.contact_id,R.occurred_at.desc().nullslast(),R.external_id))).all()
        comments={r.contact_id:serial(r) for r in rows}
    return {'items':[{**serial(r),'_latest_comment':comments.get(r.contact_id)} for r in items],'total':total,'page':page,'limit':limit}

@router.get('/activity')
async def activity(q:str=Query('',max_length=200),owner:str='',page:int=Query(1,ge=1),db:AsyncSession=Depends(get_db)):
    query=base('conversations')
    if q:query=query.where(or_(R.payload['contactName'].astext.ilike('%'+q+'%'),R.payload['fullName'].astext.ilike('%'+q+'%')))
    if owner:query=query.where(R.payload['assignedTo'].astext==owner)
    total=await db.scalar(select(func.count()).select_from(query.subquery()))
    rows=(await db.scalars(query.order_by(R.occurred_at.desc().nullslast(),R.external_id).offset((page-1)*24).limit(24))).all()
    return {'items':[serial(r) for r in rows],'total':total,'page':page,'limit':24}

@router.get('/numbers')
async def numbers(db:AsyncSession=Depends(get_db)):
    rows=(await db.scalars(select(R).where(R.location_id==loc(),R.kind=='numbers').order_by(R.active.desc(),R.payload['phoneNumber'].astext))).all()
    return {'items':[serial(r) for r in rows]}

@router.get('/calls')
async def calls(page:int=Query(1,ge=1),db:AsyncSession=Depends(get_db)):
    query=base('calls').where(R.payload['trialCall'].astext.is_distinct_from('true'))
    count=await db.scalar(select(func.count()).select_from(query.subquery()))
    rows=(await db.scalars(query.order_by(R.occurred_at.desc().nullslast()).offset((page-1)*30).limit(30))).all()
    return {'items':[serial(r) for r in rows],'total':count,'page':page,'limit':30}

@router.get('/analyses')
async def analyses(page:int=Query(1,ge=1),concerns:bool=False,db:AsyncSession=Depends(get_db)):
    query=select(SalesAnalysis).where(SalesAnalysis.location_id==loc())
    if concerns:query=query.where(SalesAnalysis.payload['outcome'].astext=='review_needed')
    count=await db.scalar(select(func.count()).select_from(query.subquery()))
    rows=(await db.scalars(query.order_by(SalesAnalysis.created_at.desc()).offset((page-1)*20).limit(20))).all()
    ids=[r.contact_id for r in rows if r.contact_id]
    contacts=(await db.scalars(base('contacts').where(R.external_id.in_(ids)))).all()
    names={r.external_id:r.payload.get('name') or ' '.join(filter(None,[r.payload.get('firstName'),r.payload.get('lastName')])) for r in contacts}
    return {'items':[{'id':r.source_id,'contact_id':r.contact_id,'contact_name':names.get(r.contact_id),'created_at':r.created_at,**r.payload} for r in rows],'total':count,'page':page,'limit':20}

@router.get('/contacts/{contact_id}')
async def contact(contact_id:str,db:AsyncSession=Depends(get_db)):
    # Only IDs already discovered in this location may schedule upstream reads.
    existing=await db.scalar(select(R).where(R.location_id==loc(),or_(R.contact_id==contact_id,(R.kind=='contacts')&(R.external_id==contact_id))).limit(1))
    if not existing:raise HTTPException(404,'Contact is not present in the synchronized location.')
    contact_row=await get_record(db,'contacts',contact_id)
    state=await db.get(SalesSync,(loc(),'contact:'+contact_id))
    if not state or not state.last_success or now()-state.last_success>timedelta(minutes=5):
        await enqueue(db,'contact',contact_id,priority=50)
    # Existing cached conversations are enough for most records; discover on demand otherwise.
    conversations=(await db.scalars(base('conversations').where(R.contact_id==contact_id))).all()
    if not conversations:
        await enqueue(db,'discover',contact_id,priority=50)
    for row in conversations:
        s=await db.get(SalesSync,(loc(),'messages:'+row.external_id))
        if not s or not s.last_success or now()-s.last_success>timedelta(seconds=60):
            await enqueue(db,'messages',row.external_id,{'id':row.external_id,'contactId':contact_id},priority=50)
    grouped={}
    for kind in ('opportunities','notes','tasks','calls','transcripts'):
        grouped[kind]=[serial(r) for r in (await db.scalars(base(kind).where(R.contact_id==contact_id).order_by(R.occurred_at.desc().nullslast()))).all()]
    messages=(await db.scalars(base('messages').where(R.contact_id==contact_id).order_by(R.occurred_at.desc().nullslast()).limit(500))).all()
    reviews=(await db.scalars(select(SalesAnalysis).where(SalesAnalysis.location_id==loc(),SalesAnalysis.contact_id==contact_id).order_by(SalesAnalysis.created_at.desc()).limit(30))).all()
    pending=await db.scalar(select(func.count()).select_from(SalesJob).where(SalesJob.location_id==loc(),or_(SalesJob.payload['contactId'].astext==contact_id,SalesJob.key=='contact:'+contact_id,SalesJob.key=='discover:'+contact_id)))
    return {'contact':serial(contact_row) if contact_row else None,'conversations':[serial(r) for r in conversations],**grouped,'messages':[serial(r) for r in messages],
        'analyses':[{'id':r.source_id,'created_at':r.created_at,**r.payload} for r in reviews],
        'pending':pending,'history_days':settings.SALES_HISTORY_DAYS,'message_limit':500,'warning':state.error if state else None}

@router.get('/reports')
async def reports(f:dict=Depends(filters),db:AsyncSession=Depends(get_db)):
    items=(await db.scalars(base('opportunities').where(*conditions(**f)))).all()
    groups={};statuses={};total_value=Decimal(0)
    for row in items:
        p=row.payload;key=(p.get('pipelineId') or '',p.get('pipelineStageId') or '',p.get('assignedTo') or '',p.get('status') or '')
        try:value=Decimal(str(p.get('monetaryValue') or 0))
        except InvalidOperation:value=Decimal(0)
        total_value+=value;statuses[key[3]]=statuses.get(key[3],0)+1
        g=groups.setdefault(key,{'pipeline_id':key[0],'stage_id':key[1],'owner_id':key[2],'status':key[3],'count':0,'value':Decimal(0)})
        g['count']+=1;g['value']+=value
    return {'count':len(items),'value':str(total_value),'statuses':statuses,'groups':[{**g,'value':str(g['value'])} for g in groups.values()],
        'date_basis':'opportunity_created_at','history_note':'Current snapshot. Stage change history starts at integration activation; no retroactive conversion is inferred.'}

@router.get('/export')
async def export(f:dict=Depends(filters),format:str=Query('csv',pattern='^(csv|xlsx)$'),db:AsyncSession=Depends(get_db)):
    rows=(await db.scalars(base('opportunities').where(*conditions(**f)).order_by(R.occurred_at.desc()))).all()
    users={r.external_id:r.payload.get('name') for r in await records(db,'users')}
    pipelines={r.external_id:r.payload for r in await records(db,'pipelines')}
    header=['Opportunity ID','Contact ID','Opportunity','Client','Pipeline','Stage','Status','Owner','Source','Value (GHL)','Created','Updated','Synced at']
    data=[header]
    for r in rows:
        p=r.payload;pipe=pipelines.get(p.get('pipelineId'),{});stage=next((s.get('name') for s in pipe.get('stages',[]) if s.get('id')==p.get('pipelineStageId')),p.get('pipelineStageId'))
        data.append([r.external_id,r.contact_id,p.get('name'),(p.get('contact') or {}).get('name'),pipe.get('name'),stage,p.get('status'),users.get(p.get('assignedTo'),p.get('assignedTo')),p.get('source'),p.get('monetaryValue'),p.get('createdAt'),p.get('updatedAt'),r.seen_at.isoformat()])
    # Formula injection protection applies to BOTH export formats.
    def safe(v):
        s='' if v is None else str(v)
        return "'"+s if s.lstrip().startswith(('=','+','-','@')) else s
    data=[[safe(x) for x in row] for row in data]
    headers={'Content-Disposition':f'attachment; filename="wallpanels-opportunities.{format}"','Cache-Control':'no-store'}
    if format=='csv':
        out=io.StringIO();csv.writer(out).writerows(data)
        return Response('\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers=headers)
    content=await run_in_threadpool(xlsx_bytes,data)
    return Response(content,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers=headers)

def xlsx_bytes(data):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    book=Workbook();sheet=book.active;sheet.title='Opportunities'
    for row in data:sheet.append(row)
    sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
    for cell in sheet[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='466246')
    for col in sheet.columns:sheet.column_dimensions[col[0].column_letter].width=min(50,max(16,max(len(str(c.value or '')) for c in col[:100])+2))
    out=io.BytesIO();book.save(out)
    return out.getvalue()

@router.get('/recordings/{message_id}')
async def recording(message_id:str,db:AsyncSession=Depends(get_db)):
    row=await get_record(db,'messages',message_id)
    call=await db.scalar(base('calls').where(R.payload['messageId'].astext==message_id).limit(1))
    if not call and (not row or row.payload.get('messageType')!='TYPE_CALL'):raise HTTPException(404,'Call not found.')
    c=GhlClient()
    try:
        content,mime=await c.get(f'/conversations/messages/{message_id}/locations/{loc()}/recording',binary=True)
        if not mime.startswith(('audio/','application/octet-stream')):raise HTTPException(404,'Recording is not available through this API.')
        return Response(content,media_type=mime,headers={'Cache-Control':'no-store'})
    except GhlError:raise HTTPException(404,'Recording is not available through this API.') from None
    finally:await c.close()
