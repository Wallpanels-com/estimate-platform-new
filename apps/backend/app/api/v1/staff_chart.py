"""Atomic HR-authorized chart edits. Reporting is distinct from collaboration."""
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
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


class ChartInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0)
    changes: list[ManagerChange] = Field(default_factory=list, max_length=1000)
    extra_edges: list[ExtraEdge] = Field(default_factory=list, max_length=2000)
    orders: dict[Layout, list[uuid.UUID]] = Field(default_factory=dict, max_length=8)


def output(chart):
    return {'version': chart.version if chart else 0,
            'extra_edges': chart.extra_edges if chart else [],
            'orders': chart.orders if chart else {},
            'updated_by': chart.updated_by if chart else '',
            'updated_at': chart.updated_at if chart else None}


@router.get('')
async def read_chart(db: AsyncSession = Depends(get_db)):
    chart = (await db.execute(select(StaffChart).where(StaffChart.name == 'main'))).scalar_one_or_none()
    return output(chart)


@router.put('')
async def save_chart(body: ChartInput, db: AsyncSession = Depends(get_db), user=Depends(staff_access)):
    await db.execute(text('SELECT pg_advisory_xact_lock(73110911)'))
    chart = (await db.execute(select(StaffChart).where(StaffChart.name == 'main'))).scalar_one_or_none()
    if body.version != (chart.version if chart else 0):
        raise HTTPException(409, 'The organization chart has changed. Cancel this draft and reload before saving.')
    rows = {r.id: r for r in (await db.execute(select(StaffMember))).scalars()}
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
    # Validate everything before mutating either employees or chart settings.
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
    chart.version += 1
    chart.updated_by = user.name or user.email
    await db.flush()
    await db.refresh(chart)
    return output(chart)
