"""Atomic HR-authorized chart edits. Reporting is distinct from collaboration."""
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.staff import staff_access
from app.core.database import get_db
from app.models.staff import StaffMember, StaffChart

router = APIRouter(prefix='/chart', tags=['Staff chart'], dependencies=[Depends(staff_access)])
Layout = Literal['tree','horizontal','orbit','departments','terraces','teams','holi','compact']


class ManagerChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: uuid.UUID
    version: int = Field(ge=1)
    manager_id: uuid.UUID | None


class ExtraEdge(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: uuid.UUID
    target: uuid.UUID


class NewStaff(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: uuid.UUID
    name: str = Field(min_length=1, max_length=240)
    status: Literal['active', 'inactive', 'paused'] = 'active'
    title: str = Field(default='', max_length=240)
    department: str = Field(default='', max_length=160)
    manager_id: uuid.UUID | None = None
    contact: str = Field(default='', max_length=500)
    email: str = Field(default='', max_length=320)
    notes: str = Field(default='', max_length=20000)

    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        if not value.strip(): return ''
        from email_validator import validate_email
        return validate_email(value.strip(), check_deliverability=False).normalized


class CardPosition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    x: float = Field(ge=-1000000, le=1000000, allow_inf_nan=False)
    y: float = Field(ge=-1000000, le=1000000, allow_inf_nan=False)


class ChartInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0)
    changes: list[ManagerChange] = Field(default_factory=list, max_length=1000)
    extra_edges: list[ExtraEdge] = Field(default_factory=list, max_length=2000)
    orders: dict[Layout, list[uuid.UUID]] = Field(default_factory=dict, max_length=8)
    new_staff: list[NewStaff] = Field(default_factory=list, max_length=20)
    # Omitted by older clients: preserve their existing layout on a link-only save.
    positions: dict[Layout, dict[uuid.UUID, CardPosition]] | None = Field(default=None, max_length=8)


def output(chart):
    return {'version': chart.version if chart else 0,
            'extra_edges': chart.extra_edges if chart else [],
            'orders': chart.orders if chart else {},
            'positions': chart.positions if chart else {},
            'updated_by': chart.updated_by if chart else '',
            'updated_at': chart.updated_at if chart else None}


@router.get('')
async def read_chart(db: AsyncSession = Depends(get_db)):
    chart = (await db.execute(select(StaffChart).where(StaffChart.name == 'main'))).scalar_one_or_none()
    return output(chart)


@router.put('')
async def save_chart(body: ChartInput, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db), user=Depends(staff_access)):
    await db.execute(text('SELECT pg_advisory_xact_lock(73110911)'))
    chart = (await db.execute(select(StaffChart).where(StaffChart.name == 'main'))).scalar_one_or_none()
    if body.version != (chart.version if chart else 0):
        raise HTTPException(409, 'The organization chart has changed. Cancel this draft and reload before saving.')
    rows = {r.id: r for r in (await db.execute(select(StaffMember))).scalars()}
    created = []
    for person in body.new_staff:
        if person.id in rows or not person.name.strip():
            raise HTTPException(422, 'Enter a new employee name and a unique employee ID.')
        member = StaffMember(id=person.id, source_key='manual:'+person.id.hex,
            source={'type':'manual','sheet':'Manual'}, name=person.name.strip(), status=person.status,
            title=person.title.strip(), department=person.department.strip(), manager_id=person.manager_id,
            fields={'A':person.name.strip(),'B':person.status.title(),'E':person.title.strip(),
                    'F':person.contact.strip(),'G':person.department.strip(),'K':person.email,'N':person.notes.strip()},
            links={}, version=1, updated_by=user.name or user.email)
        rows[member.id] = member
        created.append(member)
    ids = set(rows)
    parents = {r.id: r.manager_id for r in rows.values()}
    changed_ids = [c.id for c in body.changes]
    if len(set(changed_ids)) != len(changed_ids):
        raise HTTPException(422, 'Duplicate manager changes are not allowed.')
    for change in body.changes:
        if change.id not in ids or (change.manager_id is not None and change.manager_id not in ids):
            raise HTTPException(422, 'A selected employee no longer exists.')
        if rows[change.id].version != change.version:
            raise HTTPException(409, 'An employee in this chart has changed. Cancel this draft and reload before saving.')
        parents[change.id] = change.manager_id
    if any(parent is not None and parent not in ids for parent in parents.values()):
        raise HTTPException(422, 'The selected manager does not exist.')
    for ident in ids:
        seen = set()
        parent = ident
        while parent is not None:
            if parent in seen:
                raise HTTPException(422, 'Reporting lines cannot form a cycle. Use an additional connection instead.')
            seen.add(parent)
            parent = parents.get(parent)
    edges = [(e.source,e.target) for e in body.extra_edges]
    if len(set(edges)) != len(edges) or any(s == t or s not in ids or t not in ids or parents.get(t) == s for s,t in edges):
        raise HTTPException(422, 'Additional connections must link two different existing employees without duplicates.')
    for order in body.orders.values():
        if len(order) > 1000 or len(order) != len(set(order)) or not set(order).issubset(ids):
            raise HTTPException(422, 'Invalid card order.')
    for positions in (body.positions or {}).values():
        if len(positions) > 1000 or not set(positions).issubset(ids):
            raise HTTPException(422, 'Invalid employee card positions.')
    # Validate everything before mutating either employees or chart settings.
    # Insert new managers before pointing existing employees at them. The ORM
    # cannot order a self-referencing FK from manager_id scalar values alone.
    pending = {r.id:r for r in created}
    while pending:
        ready = [r for r in pending.values() if parents[r.id] not in pending]
        for member in ready:
            member.manager_id = parents[member.id]
            db.add(member)
            await db.flush([member])
            pending.pop(member.id)
    for change in body.changes:
        row = rows[change.id]
        if row.manager_id != change.manager_id:
            row.manager_id = change.manager_id
            row.version += 1
            row.updated_by = user.name or user.email
    if chart is None:
        chart = StaffChart(id=uuid.uuid4(), name='main', version=0)
        db.add(chart)
    chart.extra_edges = [{'source':str(s),'target':str(t)} for s,t in edges]
    chart.orders = {layout:[str(ident) for ident in order] for layout,order in body.orders.items()}
    if body.positions is not None:
        chart.positions = {layout:{str(ident):point.model_dump() for ident,point in positions.items()}
                           for layout,positions in body.positions.items()}
    chart.version += 1
    chart.updated_by = user.name or user.email
    await db.flush()
    await db.refresh(chart)
    from app.api.v1.staff import output as staff_output, schedule_avatars
    schedule_avatars(background_tasks, created)
    return output(chart) | ({'created_staff':[staff_output(r) for r in created]} if created else {})
