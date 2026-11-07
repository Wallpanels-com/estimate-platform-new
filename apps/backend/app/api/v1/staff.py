"""Owner-only employee workspace. HR page access alone never grants access."""
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.staff import StaffMember
from app.models.governance import AuditEvent
from app.services.page_access import is_access_manager
from app.services.staff_import import parse_main, initial_reporting, safe_link, COLUMNS
from app.services.hr_import import MAX_BYTES


async def owner(response: Response, user=Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    if not is_access_manager(user):
        raise HTTPException(403, 'The staff directory is currently available only to the platform owner.')
    return user


router = APIRouter(prefix='/staff', tags=['Staff'], dependencies=[Depends(owner)])


def output(r):
    return {k: getattr(r, k) for k in ('id', 'name', 'status', 'title', 'department', 'fields', 'links', 'manager_id', 'version', 'updated_by', 'created_at', 'updated_at')} | {'source_row': r.source.get('row'), 'source_sheet': 'Main'}


from app.api.v1.staff_chart import router as chart_router
router.include_router(chart_router)


@router.get('')
async def staff(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(StaffMember).order_by(StaffMember.name, StaffMember.id))).scalars().all()
    return {'items': [output(r) for r in rows], 'columns': COLUMNS}


@router.post('/import', status_code=201)
async def import_main(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), user=Depends(owner)):
    if not (file.filename or '').lower().endswith('.xlsx'):
        raise HTTPException(422, 'Upload an .xlsx workbook with a Main worksheet.')
    try:
        records = await run_in_threadpool(parse_main, await file.read(MAX_BYTES + 1))
    except Exception as e:
        raise HTTPException(422, str(e) if isinstance(e, ValueError) else 'Cannot read this workbook.') from e
    # Serialize imports/manager edits without locking or touching estimates.
    await db.execute(text('SELECT pg_advisory_xact_lock(73110911)'))
    existing = {r.source_key: r for r in (await db.execute(select(StaffMember))).scalars()}
    reporting = initial_reporting(records)
    added = []
    for r in records:
        if r['source_key'] not in existing:
            member = StaffMember(id=uuid.uuid4(), **r, updated_by=user.name or user.email, version=1)
            db.add(member)
            existing[r['source_key']] = member
            added.append(member)
    await db.flush()
    for r in added:
        key = reporting.get(r.source_key)
        r.manager_id = existing[key].id if key and key in existing else None
    await db.flush()
    return {'added': len(added), 'duplicates': len(records) - len(added), 'sheet': 'Main'}


class StaffInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=240)
    status: Literal['active', 'inactive', 'paused']
    title: str = Field(max_length=240)
    department: str = Field(max_length=160)
    manager_id: uuid.UUID | None = None
    fields: dict[str, str]
    links: dict[str, str]

    @field_validator('fields', 'links')
    @classmethod
    def bounded_fields(cls, value):
        if len(value) > 100 or any(not k.isalpha() or len(k) > 2 or not k.isupper() or len(v) > 20000 for k, v in value.items()):
            raise ValueError('Invalid staff fields.')
        return value

    @field_validator('links')
    @classmethod
    def valid_links(cls, value):
        if any(not safe_link(v) for v in value.values()):
            raise ValueError('Links must use http, https or mailto.')
        return value


@router.patch('/{ident}')
async def edit_staff(ident: uuid.UUID, body: StaffInput, db: AsyncSession = Depends(get_db), user=Depends(owner)):
    await db.execute(text('SELECT pg_advisory_xact_lock(73110911)'))
    rows = {r.id: r for r in (await db.execute(select(StaffMember))).scalars()}
    member = rows.get(ident)
    if member is None:
        raise HTTPException(404, 'Employee not found.')
    if member.version != body.version:
        raise HTTPException(409, 'This employee has changed. Close and reopen the card before saving.')
    if not body.name.strip():
        raise HTTPException(422, 'Enter an employee name.')
    parent = body.manager_id
    seen = {ident}
    while parent is not None:
        if parent in seen:
            raise HTTPException(422, 'This reporting line would create a cycle. Choose another manager.')
        if parent not in rows:
            raise HTTPException(422, 'The selected manager does not exist.')
        seen.add(parent)
        parent = rows[parent].manager_id
    for key, value in body.model_dump(exclude={'version'}).items():
        setattr(member, key, value.strip() if isinstance(value, str) else value)
    member.fields = member.fields | {'A': member.name, 'B': member.status.title(), 'E': member.title, 'G': member.department}
    member.version += 1
    member.updated_by = user.name or user.email
    await db.flush()
    await db.refresh(member)
    return output(member)


@router.get('/{ident}/history')
async def history(ident: uuid.UUID, db: AsyncSession = Depends(get_db)):
    if not await db.get(StaffMember, ident):
        raise HTTPException(404, 'Employee not found.')
    rows = (await db.execute(select(AuditEvent).where(AuditEvent.entity == 'hr_staff', AuditEvent.entity_id == str(ident)).order_by(AuditEvent.created_at.desc()).limit(50))).scalars().all()
    return [{'id': r.id, 'actor_name': r.actor_name, 'created_at': r.created_at, 'action': r.action, 'fields': list(r.changes)} for r in rows]
