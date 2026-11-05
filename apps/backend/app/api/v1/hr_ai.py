"""HR-only review endpoints; generation never edits candidate status or ranking."""
import asyncio
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.hr import Candidate, Vacancy, CandidateAIReview
from app.services import hr_ai

router=APIRouter()
_capacity=asyncio.Semaphore(2)
class GenerateInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    refresh: bool=False
class DraftInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message: str=Field(min_length=1,max_length=6000)
    expected_updated_at: datetime

def output(review, source):
    if not review:return None
    return {'content':review.content,'message_draft':review.message_draft,'model':review.model,'created_by':review.created_by,'created_at':review.created_at,'updated_at':review.updated_at,'stale':review.source_hash!=hr_ai.fingerprint(source)}

async def records(db, ident):
    c=await db.get(Candidate,ident)
    if not c:raise HTTPException(404,'Candidate not found.')
    v=await db.get(Vacancy,c.vacancy_id)
    return c,v

@router.get('/candidates/{ident}/ai')
async def get_review(ident:uuid.UUID,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    c,v=await records(db,ident)
    review=await db.get(CandidateAIReview,ident)
    return {'enabled':bool(settings.GROQ_API_KEY),'review':output(review,hr_ai.source_data(c,v))}

@router.post('/candidates/{ident}/ai')
async def generate(ident:uuid.UUID,body:GenerateInput,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    # Transaction lock is shared across all workers; duplicate clicks cannot create duplicate API calls.
    locked=(await db.execute(text('SELECT pg_try_advisory_xact_lock(:key)'),{'key':int(ident.hex[:15],16)})).scalar_one()
    if not locked:raise HTTPException(409,'AI review is already being prepared. Reopen the card shortly.')
    c,v=await records(db,ident);source=hr_ai.source_data(c,v)
    review=await db.get(CandidateAIReview,ident)
    source_hash=hr_ai.fingerprint(source)
    if review and review.source_hash==source_hash and not body.refresh:return {'enabled':bool(settings.GROQ_API_KEY),'review':output(review,source)}
    if review and body.refresh and (datetime.now(timezone.utc)-review.created_at).total_seconds()<30:
        raise HTTPException(429,'Please wait 30 seconds before generating a new review.')
    try:
        await asyncio.wait_for(_capacity.acquire(),timeout=0.1)
    except TimeoutError:raise HTTPException(429,'AI is processing other applications. Try again shortly.') from None
    try:
        content=await hr_ai.generate_review(source)
    except hr_ai.AIUnavailable as e:raise HTTPException(e.status,e.message) from None
    finally:_capacity.release()
    # Refuse a stale result if another user edited the application/job during generation.
    await db.refresh(c);await db.refresh(v)
    if hr_ai.fingerprint(hr_ai.source_data(c,v))!=source_hash:
        raise HTTPException(409,'Application or requirements changed during analysis. Generate a fresh review.')
    message=content['message_uk'].replace('{{recruiter_name}}',user.name or user.email).replace('{{vacancy_name}}',v.name)
    if '{{recruiter_name}}' not in content['message_uk']:
        message='Вітаю!\nМене звати '+(user.name or user.email)+', я рекрутер Wallpanels.com.\n\n'+message.removeprefix('Вітаю!').lstrip()
    content['message_uk']=message
    now=datetime.now(timezone.utc)
    if review:
        edited=review.message_draft!=review.content.get('message_uk')
        if not edited:review.message_draft=message
        review.content=content;review.source_hash=source_hash;review.model=settings.HR_AI_MODEL
        review.created_by=user.name or user.email;review.created_at=now;review.updated_at=now
    else:
        review=CandidateAIReview(candidate_id=ident,source_hash=source_hash,content=content,message_draft=message,model=settings.HR_AI_MODEL,created_by=user.name or user.email,created_at=now,updated_at=now)
        db.add(review)
    await db.flush();return {'enabled':True,'review':output(review,source)}

@router.patch('/candidates/{ident}/ai/message')
async def save_draft(ident:uuid.UUID,body:DraftInput,db:AsyncSession=Depends(get_db),user=Depends(get_current_user)):
    # Same lock as generation so an edited draft cannot be lost on refresh.
    locked=(await db.execute(text('SELECT pg_try_advisory_xact_lock(:key)'),{'key':int(ident.hex[:15],16)})).scalar_one()
    if not locked:raise HTTPException(409,'AI review is being updated. Try saving your draft shortly.')
    c,v=await records(db,ident);review=await db.get(CandidateAIReview,ident)
    if not review:raise HTTPException(404,'Generate an AI review first.')
    if review.updated_at!=body.expected_updated_at:raise HTTPException(409,'The message changed. Reopen the card before saving; your draft has not been overwritten.')
    if not body.message.strip():raise HTTPException(422,'Enter a message.')
    review.message_draft=body.message.strip();review.updated_at=datetime.now(timezone.utc)
    await db.flush();return {'enabled':bool(settings.GROQ_API_KEY),'review':output(review,hr_ai.source_data(c,v))}
