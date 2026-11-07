"""HR-managed statuses, manual applications and private attachments."""
from pathlib import Path
from hashlib import sha256
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.hr import Candidate, Vacancy, CandidateStatus, CandidateAttachment
from app.services.hr_statuses import DEFAULT_STATUSES, ensure_statuses, status_rows, validate_status
from app.services.telegram_contacts import normalize_username
router=APIRouter()

class StatusInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name_en:str=Field(min_length=1,max_length=120)
    name_ru:str=Field(default='',max_length=120)
    version:int=Field(default=0,ge=0)
class DeleteStatus(BaseModel):
    version:int=Field(ge=1)
    replacement:str=Field(min_length=1,max_length=30)

def status_out(row, count=0):
    return {k:getattr(row,k) for k in ('key','name_en','name_ru','position','version')}|{'count':count}

@router.get('/statuses')
async def list_statuses(db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    rows=await status_rows(db)
    counts=dict((await db.execute(select(Candidate.status,func.count()).group_by(Candidate.status))).all())
    if not rows:return [dict(key=k,name_en=en,name_ru=ru,position=i,version=0,count=counts.get(k,0)) for i,(k,en,ru) in enumerate(DEFAULT_STATUSES)]
    return [status_out(r,counts.get(r.key,0)) for r in rows if not r.deleted]

@router.post('/statuses',status_code=201)
async def create_status(body:StatusInput,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    await ensure_statuses(db)
    name=body.name_en.strip()
    if not name:raise HTTPException(422,'Enter a status name.')
    rows=await status_rows(db)
    if any(not r.deleted and r.name_en.casefold()==name.casefold() for r in rows):raise HTTPException(409,'This status already exists.')
    r=CandidateStatus(key='s_'+uuid.uuid4().hex[:24],name_en=name,name_ru=body.name_ru.strip() or name,position=max((r.position for r in rows),default=0)+1,version=1,deleted=False)
    db.add(r);await db.flush();return status_out(r)

@router.patch('/statuses/{key}')
async def edit_status(key:str,body:StatusInput,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    r=await validate_status(db,key)
    # Version zero is the virtual default only in brand-new isolated workspaces.
    if body.version!=r.version and not (body.version==0 and r.version==1 and key in dict((k,en) for k,en,_ in DEFAULT_STATUSES)):raise HTTPException(409,'This status has changed. Refresh before saving.')
    name=body.name_en.strip()
    if not name:raise HTTPException(422,'Enter a status name.')
    if any(x.key!=key and not x.deleted and x.name_en.casefold()==name.casefold() for x in await status_rows(db)):raise HTTPException(409,'This status already exists.')
    r.name_en=name;r.name_ru=body.name_ru.strip() or name;r.version+=1;await db.flush();return status_out(r)

@router.delete('/statuses/{key}')
async def delete_status(key:str,body:DeleteStatus,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    r=await validate_status(db,key)
    if key=='new':raise HTTPException(409,'The incoming candidate status can be renamed but cannot be deleted.')
    if r.version!=body.version:raise HTTPException(409,'This status has changed. Refresh before saving.')
    if body.replacement==key:raise HTTPException(422,'Choose a different replacement status.')
    await validate_status(db,body.replacement)
    people=(await db.execute(select(Candidate).where(Candidate.status==key).with_for_update())).scalars().all()
    for c in people:c.status=body.replacement;c.version+=1;c.updated_by=user.name or user.email
    r.deleted=True;r.version+=1;await db.flush()
    return {'moved':len(people)}

class ManualCandidate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=240)
    email:str=Field(default='',max_length=320)
    phone:str=Field(default='',max_length=100)
    telegram_username:str|None=Field(default=None,max_length=200)
    status:str=Field(default='new',max_length=30)
    notes:str=Field(default='',max_length=20000)
    experience:str=Field(default='',max_length=10000)
    english:str=Field(default='',max_length=2000)
    us_market:str=Field(default='',max_length=2000)
    drawings:str=Field(default='',max_length=2000)
    @field_validator('telegram_username')
    @classmethod
    def handle(cls,value):return normalize_username(value)
    @field_validator('email')
    @classmethod
    def valid_email(cls,value):
        value=value.strip()
        if value:
            from email_validator import validate_email
            return validate_email(value,check_deliverability=False).normalized
        return value

@router.post('/vacancies/{ident}/candidates',status_code=201)
async def add_candidate(ident:uuid.UUID,body:ManualCandidate,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    from app.api.v1.hr import vacancy,candidate_out
    from app.services.hr_scoring import qualification_score
    v=await vacancy(db,ident,True)
    if v.archived:raise HTTPException(409,'Restore the vacancy before adding candidates.')
    if not body.name.strip():raise HTTPException(422,'Enter a candidate name.')
    if not (body.email or body.phone.strip() or body.telegram_username):raise HTTPException(422,'Enter at least one contact.')
    await validate_status(db,body.status)
    identity=body.email.lower() or re.sub(r'\D','',body.phone) or body.telegram_username
    fingerprint=sha256(('manual:'+str(identity)).encode()).hexdigest()
    duplicate=(await db.execute(select(Candidate.id).where(Candidate.vacancy_id==ident, (Candidate.fingerprint==fingerprint) | ( (func.lower(Candidate.email)==body.email.lower()) if body.email else ((Candidate.phone==body.phone.strip()) if body.phone.strip() else (Candidate.telegram_username==body.telegram_username)))).limit(1))).scalar_one_or_none()
    if duplicate:raise HTTPException(409,'A candidate with this contact already exists in this vacancy.')
    answers={k:v.strip() for k,v in [('Years of experience',body.experience),('English level',body.english),('US market',body.us_market),('Technical drawings',body.drawings)] if v.strip()}
    c=Candidate(vacancy_id=ident,name=body.name.strip(),email=body.email,phone=body.phone.strip(),telegram_username=body.telegram_username,answers=answers,source='Manual',status=body.status,notes=body.notes,priority=False,hidden=False,location='',location_verified=False,score=qualification_score(answers)['score'],updated_by=user.name or user.email,version=1,fingerprint=fingerprint)
    db.add(c);await db.flush();await db.refresh(c);return candidate_out(c)

@router.get('/candidates/{ident}/files')
async def files(ident:uuid.UUID,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    if not await db.get(Candidate,ident):raise HTTPException(404,'Candidate not found.')
    rows=(await db.execute(select(CandidateAttachment).where(CandidateAttachment.candidate_id==ident).order_by(CandidateAttachment.created_at,CandidateAttachment.id))).scalars().all()
    return [{k:getattr(r,k) for k in ('id','name','size','created_by','created_at')} for r in rows]

@router.post('/candidates/{ident}/files',status_code=201)
async def upload_file(ident:uuid.UUID,file:UploadFile=File(...),db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    if not await db.get(Candidate,ident):raise HTTPException(404,'Candidate not found.')
    folder=Path(settings.STORAGE_PATH)/'hr-files'/str(ident);folder.mkdir(parents=True,exist_ok=True)
    fid=uuid.uuid4();target=folder/str(fid);size=0
    try:
        with target.open('xb') as stream:
            while chunk:=await file.read(64*1024):
                size+=len(chunk)
                if size>20*1024*1024:raise HTTPException(413,'Maximum file size is 20 MB.')
                stream.write(chunk)
        if not size:raise HTTPException(422,'Choose a non-empty file.')
        name=re.sub(r'[\x00-\x1f\x7f]','', (file.filename or 'File').replace('\\','/').split('/')[-1])[:240] or 'File'
        r=CandidateAttachment(id=fid,candidate_id=ident,name=name,size=size,created_by=user.name or user.email)
        db.add(r);await db.flush();await db.refresh(r)
        result={k:getattr(r,k) for k in ('id','name','size','created_by','created_at')}
        await db.commit()
        return result
    except Exception:
        target.unlink(missing_ok=True);raise
    finally:await file.close()

@router.get('/candidate-files/{ident}')
async def download_file(ident:uuid.UUID,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    r=await db.get(CandidateAttachment,ident)
    if not r:raise HTTPException(404,'File not found.')
    path=Path(settings.STORAGE_PATH)/'hr-files'/str(r.candidate_id)/str(r.id)
    if not path.is_file():raise HTTPException(503,'File unavailable. Contact Dmitry.')
    return FileResponse(path,filename=r.name,media_type='application/octet-stream',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
