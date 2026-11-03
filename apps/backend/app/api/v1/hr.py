"""Authenticated HR workspace with staged, idempotent Excel imports."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, func, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.hr import Vacancy, Candidate, ImportBatch
from app.models.governance import AuditEvent
from app.services.hr_import import parse_workbook, suggest_mapping, prepare_rows, contact_flags, MAX_BYTES

from app.services.hr_scoring import qualification_score

router=APIRouter(prefix='/hr', tags=['HR'])
Status=Literal['new','review','contacted','interview','offer','hired','rejected','archived']

class VacancyInput(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    description: str = Field(default='',max_length=4000)
    archived: bool = False
    expected_updated_at: datetime | None = None

class CandidateInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: int = Field(ge=1)
    status: Status
    priority: bool
    location: str = Field(default='',max_length=240)
    location_verified: bool = False
    notes: str = Field(default='',max_length=20000)

    telegram_username: str | None = Field(default=None,max_length=200)

    @field_validator('telegram_username')
    @classmethod
    def telegram_handle(cls,value):
        from app.services.telegram_contacts import normalize_username
        return normalize_username(value)

class CandidateQuickInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)
    priority: bool | None = None
    hidden: bool | None = None

class ImportInput(BaseModel):
    sheet: str = Field(max_length=160)
    mapping: dict[str,str]

async def vacancy(db, ident, lock=False):
    q=select(Vacancy).where(Vacancy.id==ident)
    if lock:q=q.with_for_update()
    v=(await db.execute(q)).scalar_one_or_none()
    if not v:raise HTTPException(404,'Vacancy not found.')
    return v

def vacancy_out(v, count=0):
    return {k:getattr(v,k) for k in ('id','name','description','archived','created_at','updated_at')} | {'count':count}

def candidate_out(c):
    return {k:getattr(c,k) for k in ('id','vacancy_id','name','email','phone','telegram_username','answers','source','status','priority','hidden','location','location_verified','notes','updated_by','version','created_at','updated_at')} | {'contact_flags':contact_flags(c.phone,c.email), **qualification_score(c.answers)}

@router.get('/vacancies')
async def vacancies(db:AsyncSession=Depends(get_db), user=Depends(get_current_user)):
    rows=(await db.execute(select(Vacancy,func.count(Candidate.id)).outerjoin(Candidate,Candidate.vacancy_id==Vacancy.id).group_by(Vacancy.id).order_by(Vacancy.created_at,Vacancy.id))).all()
    return [vacancy_out(v,n) for v,n in rows]

@router.post('/vacancies',status_code=201)
async def create_vacancy(body:VacancyInput,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    if not body.name.strip():raise HTTPException(422,'Enter a vacancy name.')
    v=Vacancy(name=body.name.strip(),description=body.description,archived=False)
    db.add(v);await db.flush();await db.refresh(v);return vacancy_out(v)

@router.patch('/vacancies/{ident}')
async def edit_vacancy(ident:uuid.UUID,body:VacancyInput,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    v=await vacancy(db,ident,True)
    if body.expected_updated_at!=v.updated_at:raise HTTPException(409,'This vacancy has changed. Reload before saving.')
    if not body.name.strip():raise HTTPException(422,'Enter a vacancy name.')
    v.name=body.name.strip();v.description=body.description;v.archived=body.archived
    await db.flush();await db.refresh(v);return vacancy_out(v)

@router.get('/vacancies/{ident}/candidates')
async def candidates(ident:uuid.UUID,q:str=Query('',max_length=200),status:Status|None=None,priority:bool=False,hidden:bool=False,page:int=Query(1,ge=1),page_size:int=Query(50,ge=20,le=100),db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    if page_size not in (20,50,100):raise HTTPException(422,'Choose 20, 50 or 100 candidates per page.')
    await vacancy(db,ident)
    where=[Candidate.vacancy_id==ident, Candidate.hidden.is_(hidden)]
    if status:where.append(Candidate.status==status)
    else:where.append(Candidate.status!='archived')
    if priority:where.append(Candidate.priority.is_(True))
    if q.strip():
        term='%'+q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        where.append(or_(*(c.ilike(term) for c in (Candidate.name,Candidate.email,Candidate.phone))))
    total=(await db.execute(select(func.count()).select_from(Candidate).where(*where))).scalar_one()
    page=min(page,max(1,(total+page_size-1)//page_size))
    rows=(await db.execute(select(Candidate).where(*where).order_by(Candidate.priority.desc(),Candidate.score.desc().nulls_last(),Candidate.created_at.desc(),Candidate.id).offset((page-1)*page_size).limit(page_size))).scalars().all()
    counts=(await db.execute(select(Candidate.status,func.count()).where(Candidate.vacancy_id==ident).group_by(Candidate.status))).all()
    return {'items':[candidate_out(c) for c in rows],'total':total,'counts':dict(counts),'page':page,'page_size':page_size}

@router.patch('/candidates/{ident}')
async def edit_candidate(ident:uuid.UUID,body:CandidateInput,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    c=(await db.execute(select(Candidate).where(Candidate.id==ident).with_for_update())).scalar_one_or_none()
    if not c:raise HTTPException(404,'Candidate not found.')
    if body.version!=c.version:raise HTTPException(409,'This candidate has changed. Close and reopen the card before saving. Your changes have not been saved.')
    if body.location_verified and not body.location.strip():raise HTTPException(422,'Enter the confirmed location first.')
    for key,value in body.model_dump(exclude={'version','telegram_username'}).items():setattr(c,key,value)
    if 'telegram_username' in body.model_fields_set:c.telegram_username=body.telegram_username
    c.version+=1;c.updated_by=user.name or user.email
    await db.flush();await db.refresh(c);return candidate_out(c)

@router.patch('/candidates/{ident}/quick')
async def quick_candidate(ident:uuid.UUID,body:CandidateQuickInput,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    changes={k:v for k,v in body.model_dump(exclude={'version'}).items() if v is not None}
    if len(changes)!=1:raise HTTPException(422,'Choose exactly one quick action.')
    c=(await db.execute(select(Candidate).where(Candidate.id==ident).with_for_update())).scalar_one_or_none()
    if not c:raise HTTPException(404,'Candidate not found.')
    if body.version!=c.version:raise HTTPException(409,'This candidate has changed. The list has been refreshed; try again.')
    for key,value in changes.items():setattr(c,key,value)
    c.version+=1;c.updated_by=user.name or user.email
    await db.flush();await db.refresh(c)
    return candidate_out(c)

@router.get('/candidates/{ident}/history')
async def history(ident:uuid.UUID,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    if not await db.get(Candidate,ident):raise HTTPException(404,'Candidate not found.')
    rows=(await db.execute(select(AuditEvent).where(AuditEvent.entity=='hr_candidates',AuditEvent.entity_id==str(ident)).order_by(AuditEvent.created_at.desc()).limit(50))).scalars().all()
    return [{'id':r.id,'actor_name':r.actor_name,'created_at':r.created_at,'action':r.action,'fields':list(r.changes)} for r in rows]

@router.post('/vacancies/{ident}/imports',status_code=201)
async def stage_import(ident:uuid.UUID,file:UploadFile=File(...),db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    v=await vacancy(db,ident)
    if v.archived:raise HTTPException(409,'Restore the vacancy before importing.')
    if not (file.filename or '').lower().endswith('.xlsx'):raise HTTPException(422,'Upload an .xlsx workbook.')
    data=await file.read(MAX_BYTES+1)
    try:payload=await run_in_threadpool(parse_workbook,data)
    except Exception as e:
        if isinstance(e,ValueError):raise HTTPException(422,str(e)) from e
        raise HTTPException(422,'Cannot read this workbook. Save it as .xlsx and try again.') from e
    # Discard expired staging payloads only; committed candidate records remain intact.
    await db.execute(delete(ImportBatch).where(ImportBatch.result.is_(None),ImportBatch.created_at < datetime.now(timezone.utc)-timedelta(days=1)))
    batch=ImportBatch(vacancy_id=ident,filename=(file.filename or 'Candidates.xlsx')[:240],payload=payload)
    db.add(batch);await db.flush()
    return {'id':batch.id,'sheets':[{'name':s['name'],'columns':s['columns'],'count':len(s['rows']),'sample':s['rows'][:3],'mapping':suggest_mapping(s['columns'])} for s in payload['sheets']]}

async def load_batch(db,ident,body,lock=False):
    query=select(ImportBatch).where(ImportBatch.id==ident)
    if lock:query=query.with_for_update()
    batch=(await db.execute(query)).scalar_one_or_none()
    if not batch:raise HTTPException(404,'Import not found. Upload the file again.')
    if batch.result:return batch,None,None
    if (datetime.now(timezone.utc)-batch.created_at).total_seconds()>86400:raise HTTPException(410,'Import preview expired. Upload the file again.')
    sheet=next((s for s in batch.payload['sheets'] if s['name']==body.sheet),None)
    if not sheet:raise HTTPException(422,'Choose a worksheet.')
    if set(body.mapping)!={'name','email','phone'} or not body.mapping['name'] or not (body.mapping['email'] or body.mapping['phone']) or any(x and x not in sheet['columns'] for x in body.mapping.values()):raise HTTPException(422,'Map name and at least one contact column.')
    rows,info=prepare_rows(sheet['rows'],body.mapping)
    return batch,rows,info

async def existing_keys(db,vacancy_id):
    return set((await db.execute(select(Candidate.fingerprint).where(Candidate.vacancy_id==vacancy_id))).scalars())

@router.post('/imports/{ident}/preview')
async def preview_import(ident:uuid.UUID,body:ImportInput,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    batch,rows,info=await load_batch(db,ident,body)
    if batch.result:return batch.result
    seen=await existing_keys(db,batch.vacancy_id);fresh=[];duplicates=0
    for row in rows:
        if row['fingerprint'] in seen:duplicates+=1
        else:fresh.append(row);seen.add(row['fingerprint'])
    return info|{'added':len(fresh),'duplicates':duplicates,'sample':[{'name':r['name'],'email':r['email'],'phone':r['phone']} for r in fresh[:5]]}

@router.post('/imports/{ident}/confirm')
async def confirm_import(ident:uuid.UUID,body:ImportInput,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    batch,rows,info=await load_batch(db,ident,body,True)
    if batch.result:return batch.result
    v=await vacancy(db,batch.vacancy_id,True)  # serialize imports into the same vacancy
    if v.archived:raise HTTPException(409,'Restore the vacancy before importing.')
    seen=await existing_keys(db,batch.vacancy_id);added=duplicates=0
    for row in rows:
        if row['fingerprint'] in seen:duplicates+=1;continue
        db.add(Candidate(vacancy_id=batch.vacancy_id,source=batch.filename,updated_by=user.name or user.email,score=qualification_score(row["answers"])["score"],**row))
        seen.add(row['fingerprint']);added+=1
    batch.result=info|{'added':added,'duplicates':duplicates}
    batch.payload={}  # candidate answers are now durable; do not keep a second copy
    await db.flush();return batch.result
