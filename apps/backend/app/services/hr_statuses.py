"""Shared editable HR workflow; status codes remain stable across renaming."""
from sqlalchemy import select, text
from fastapi import HTTPException
from app.models.hr import CandidateStatus
DEFAULT_STATUSES = [
 ('new','New candidate','Новый кандидат'),('review','In review','На рассмотрении'),
 ('contacted','Contacted','Связались'),('interview','Interview','Собеседование'),
 ('offer','Offer','Предложение'),('hired','Hired','Нанят'),
 ('rejected','Not selected','Не выбран'),('archived','Archived','В архиве')]

async def status_rows(db):
    return (await db.execute(select(CandidateStatus).order_by(CandidateStatus.position, CandidateStatus.key))).scalars().all()

async def ensure_statuses(db):
    await db.execute(text('SELECT pg_advisory_xact_lock(73110912)'))
    if not await status_rows(db):
        db.add_all([CandidateStatus(key=k,name_en=en,name_ru=ru,position=i,version=1,deleted=False) for i,(k,en,ru) in enumerate(DEFAULT_STATUSES)])
        await db.flush()

async def validate_status(db, key):
    await ensure_statuses(db)
    row=await db.get(CandidateStatus,key)
    if not row or row.deleted:raise HTTPException(422,'Choose an available candidate status.')
    return row
