from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sa_delete, func
from sqlalchemy.orm import selectinload
from typing import List
import uuid
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.models.user import User
from app.models.estimate import Estimate, EstimateZone, LineItem
from app.schemas.estimate import (
    EstimateCreate, EstimateUpdate, EstimateOut, EstimateListItem,
    LineItemCreate, LineItemUpdate, LineItemOut, ReorderRequest
)
from app.api.deps import get_current_user
from app.services.estimate_branches import switch_mode, synchronize
from pydantic import BaseModel, Field
from app.services.final_zone_photos import select_photo

router = APIRouter(prefix="/estimates", tags=["estimates"])


def recalc_totals(estimate: Estimate) -> None:
    # Sum all line items belonging to this estimate (both zone-linked and direct)
    subtotal = sum((item.total_price for item in estimate.line_items), type(estimate.subtotal)("0")) \
        if estimate.line_items else type(estimate.subtotal)("0")
    estimate.subtotal = subtotal
    if not estimate.manual_override:
        estimate.final_total = subtotal


def user_display_name(user: User) -> str:
    return user.name or user.email


def touch(estimate: Estimate, user: User) -> None:
    """Record who last modified this estimate."""
    estimate.updated_by_name = user_display_name(user)


async def load_estimate(estimate_id: uuid.UUID, user: User, db: AsyncSession) -> Estimate:
    # Serialize edits and inheritance on the shared Pre row. Both branches take
    # this lock before touching children, avoiding stale override snapshots.
    source = (await db.execute(select(Estimate.source_estimate_id).where(Estimate.id == estimate_id))).scalar_one_or_none()
    await db.execute(select(Estimate.id).where(Estimate.id == (source or estimate_id)).with_for_update())
    result = await db.execute(
        select(Estimate)
        .options(
            selectinload(Estimate.line_items),
            selectinload(Estimate.images),
            selectinload(Estimate.zones).selectinload(EstimateZone.line_items),
            selectinload(Estimate.zones).selectinload(EstimateZone.images),
        )
        .where(Estimate.id == estimate_id)
        .execution_options(populate_existing=True)
    )
    est = result.scalar_one_or_none()
    if not est:
        raise HTTPException(status_code=404, detail="Estimate not found")
    return est


TRASH_RETENTION_DAYS = 7


async def _purge_expired_trash(db: AsyncSession) -> None:
    """Hard-delete estimates that have been in the trash for more than the retention period."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=TRASH_RETENTION_DAYS)
    await db.execute(
        sa_delete(Estimate).where(Estimate.deleted_at.isnot(None), Estimate.deleted_at < cutoff)
    )
    await db.commit()


@router.get("", response_model=List[EstimateListItem])
async def list_estimates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _purge_expired_trash(db)
    result = await db.execute(
        select(Estimate)
        .where(Estimate.deleted_at.is_(None), Estimate.source_estimate_id.is_(None))
        .order_by(Estimate.updated_at.desc())
    )
    items = []
    for est in result.scalars().all():
        if (est.branch_state or {}).get('active_mode') == 'final':
            final = (await db.execute(select(Estimate).where(Estimate.source_estimate_id == est.id))).scalar_one_or_none()
            if final: est = final
        item = EstimateListItem.model_validate(est)
        item.created_by = est.created_by_name
        item.updated_by = est.updated_by_name
        items.append(item)
    return items


@router.get("/trash", response_model=List[EstimateListItem])
async def list_trash(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _purge_expired_trash(db)
    result = await db.execute(
        select(Estimate)
        .where(Estimate.deleted_at.isnot(None), Estimate.source_estimate_id.is_(None))
        .order_by(Estimate.deleted_at.desc())
    )
    items = []
    for est in result.scalars().all():
        if (est.branch_state or {}).get('active_mode') == 'final':
            final = (await db.execute(select(Estimate).where(Estimate.source_estimate_id == est.id))).scalar_one_or_none()
            if final: est = final
        item = EstimateListItem.model_validate(est)
        item.created_by = est.created_by_name
        item.updated_by = est.updated_by_name
        items.append(item)
    return items


@router.post("", response_model=EstimateOut, status_code=201)
async def create_estimate(
    data: EstimateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = user_display_name(current_user)
    values = data.model_dump()
    values['prepared_by'] = name
    est = Estimate(**values, user_id=current_user.id, created_by_name=name, updated_by_name=name)
    db.add(est)
    await db.flush()
    # Auto-create one empty zone for pre/final estimates only
    # Quick estimates create their own zones from room templates
    if est.type != 'quick':
        zone = EstimateZone(estimate_id=est.id, sort_order=0, zone_type="wall", label="Zone 1")
        db.add(zone)
        await db.flush()
    await db.commit()
    return await load_estimate(est.id, current_user, db)


@router.get("/{estimate_id}", response_model=EstimateOut)
async def get_estimate(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    est = await load_estimate(estimate_id, current_user, db)
    if est.source_estimate_id:
        est = await synchronize(db, est)
        await db.commit()
        est = await load_estimate(est.id, current_user, db)
    return est


class ModeRequest(BaseModel):
    mode: str


@router.post("/{estimate_id}/mode", response_model=EstimateOut)
async def change_mode(estimate_id: uuid.UUID, data: ModeRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if data.mode not in ('pre', 'final'):
        raise HTTPException(400, 'Choose Pre-estimate or Final Estimate.')
    est = await load_estimate(estimate_id, current_user, db)
    return await switch_mode(db, est, data.mode)


class CoverRequest(BaseModel):
    image_id: uuid.UUID


class ZonePhotoRequest(BaseModel):
    slot: int = Field(ge=1, le=4, strict=True)


@router.put("/{estimate_id}/zones/{zone_id}/presentation-photo", response_model=EstimateOut)
async def set_zone_photo(estimate_id: uuid.UUID, zone_id: uuid.UUID, data: ZonePhotoRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    est = await load_estimate(estimate_id, current_user, db)
    if est.type != 'final':
        raise HTTPException(400, 'Presentation photos are selected in Final Estimate.')
    if est.source_estimate_id:
        est = await synchronize(db, est)
    zone = next((zone for zone in est.zones if zone.id == zone_id), None)
    if zone is None:
        raise HTTPException(404, 'Zone not found in this Final Estimate.')
    try:
        select_photo(est, zone, data.slot)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    touch(est, current_user)
    est.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await load_estimate(estimate_id, current_user, db)


@router.put("/{estimate_id}/cover-photo", response_model=EstimateOut)
async def set_cover(estimate_id: uuid.UUID, data: CoverRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    est = await load_estimate(estimate_id, current_user, db)
    if est.type != 'final':
        raise HTTPException(400, 'Cover photos are selected in Final Estimate.')
    if str(data.image_id) not in {str(i.id) for i in est.images}:
        raise HTTPException(400, 'Choose a photo from this Final Estimate.')
    est.cover_image_id = str(data.image_id)
    touch(est, current_user)
    est.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await load_estimate(estimate_id, current_user, db)


@router.patch("/{estimate_id}", response_model=EstimateOut)
async def update_estimate(
    estimate_id: uuid.UUID,
    data: EstimateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    est = await load_estimate(estimate_id, current_user, db)
    fields = data.model_dump(exclude_unset=True)
    if fields.get('type') in ('pre', 'final') and fields['type'] != est.type:
        est = await switch_mode(db, est, fields.pop('type'))
        estimate_id = est.id
    for field, value in fields.items():
        setattr(est, field, value)
    touch(est, current_user)
    await db.flush()
    await db.commit()
    return await load_estimate(estimate_id, current_user, db)


@router.delete("/{estimate_id}", status_code=204)
async def delete_estimate(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft delete - moves the estimate to the Trash (kept for 7 days, then purged)."""
    est = await load_estimate(estimate_id, current_user, db)
    root_id = est.source_estimate_id or est.id
    versions = (await db.execute(select(Estimate).where((Estimate.id == root_id) | (Estimate.source_estimate_id == root_id)))).scalars().all()
    for version in versions:
        version.deleted_at = datetime.now(timezone.utc)
        touch(version, current_user)
    await db.commit()


@router.post("/{estimate_id}/restore", response_model=EstimateOut)
async def restore_estimate(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    est = await load_estimate(estimate_id, current_user, db)
    root_id = est.source_estimate_id or est.id
    versions = (await db.execute(select(Estimate).where((Estimate.id == root_id) | (Estimate.source_estimate_id == root_id)))).scalars().all()
    for version in versions:
        version.deleted_at = None
        touch(version, current_user)
    await db.commit()
    return await load_estimate(estimate_id, current_user, db)


@router.delete("/{estimate_id}/permanent", status_code=204)
async def permanently_delete_estimate(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    est = await load_estimate(estimate_id, current_user, db)
    if est.source_estimate_id:
        est = await load_estimate(est.source_estimate_id, current_user, db)
    await db.delete(est)
    await db.commit()


@router.post("/{estimate_id}/duplicate", response_model=EstimateOut, status_code=201)
async def duplicate_estimate(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    src = await load_estimate(estimate_id, current_user, db)
    new_est = Estimate(
        user_id=current_user.id,
        type=src.type,
        title=f"{src.title or 'Estimate'} (copy)",
        client_name=src.client_name,
        project_name=src.project_name,
        prepared_by=src.prepared_by,
        notes=src.notes,
        status="draft",
    )
    db.add(new_est)
    await db.flush()

    for zone in src.zones:
        new_zone = EstimateZone(
            estimate_id=new_est.id,
            sort_order=zone.sort_order,
            zone_type=zone.zone_type,
            label=zone.label,
            room_name=zone.room_name,
            wall_name=zone.wall_name,
            wall_width_ft=zone.wall_width_ft,
            wall_height_ft=zone.wall_height_ft,
            square_footage=zone.square_footage,
            linear_footage=zone.linear_footage,
            notes=zone.notes,
        )
        db.add(new_zone)
        await db.flush()
        for item in zone.line_items:
            db.add(LineItem(
                estimate_id=new_est.id, zone_id=new_zone.id,
                section=item.section, sort_order=item.sort_order, name=item.name,
                description=item.description, calc_type=item.calc_type,
                quantity=item.quantity, unit=item.unit, unit_price=item.unit_price,
                total_price=item.total_price,
            ))

    # Direct (non-zone) line items
    for item in src.line_items:
        if item.zone_id is None:
            db.add(LineItem(
                estimate_id=new_est.id, zone_id=None,
                section=item.section, sort_order=item.sort_order, name=item.name,
                description=item.description, calc_type=item.calc_type,
                quantity=item.quantity, unit=item.unit, unit_price=item.unit_price,
                total_price=item.total_price,
            ))

    await db.flush()
    new_est_full = await load_estimate(new_est.id, current_user, db)
    recalc_totals(new_est_full)
    await db.commit()
    return await load_estimate(new_est.id, current_user, db)


# ---- Line Items (direct on estimate, no zone) ----

@router.get("/{estimate_id}/line-items", response_model=List[LineItemOut])
async def list_line_items(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    est = await load_estimate(estimate_id, current_user, db)
    return est.line_items


@router.post("/{estimate_id}/line-items", response_model=LineItemOut, status_code=201)
async def create_line_item(
    estimate_id: uuid.UUID,
    data: LineItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    est = await load_estimate(estimate_id, current_user, db)
    total = data.total_price
    if (data.calc_type in ("sf", "lf") and data.quantity is not None
            and data.unit_price is not None and "total_price" not in data.model_fields_set):
        total = data.quantity * data.unit_price
    dump = data.model_dump()
    # Snapshot unit_price at creation if not explicitly provided
    if dump.get("original_unit_price") is None and dump.get("unit_price") is not None:
        dump["original_unit_price"] = dump["unit_price"]
    item = LineItem(estimate_id=est.id, **{**dump, "total_price": total})
    db.add(item)
    await db.flush()
    await db.commit()
    est = await load_estimate(estimate_id, current_user, db)
    recalc_totals(est)
    touch(est, current_user)
    await db.commit()
    result = await db.execute(select(LineItem).where(LineItem.id == item.id))
    return result.scalar_one()


@router.patch("/{estimate_id}/line-items/{item_id}", response_model=LineItemOut)
async def update_line_item(
    estimate_id: uuid.UUID,
    item_id: uuid.UUID,
    data: LineItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await load_estimate(estimate_id, current_user, db)
    result = await db.execute(
        select(LineItem).join(Estimate).where(
            LineItem.id == item_id, LineItem.estimate_id == estimate_id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")
    fields = data.model_dump(exclude_unset=True)
    for field, value in fields.items():
        setattr(item, field, value)
    # Derive total = quantity x unit_price for ANY calc type (sf/lf/fixed/manual),
    # unless the user is explicitly editing total_price in this request — that is
    # a manual override and must be preserved.
    if "total_price" not in fields and item.quantity is not None and item.unit_price is not None:
        item.total_price = item.quantity * item.unit_price
    await db.flush()
    await db.commit()
    est = await load_estimate(estimate_id, current_user, db)
    recalc_totals(est)
    touch(est, current_user)
    await db.commit()
    result = await db.execute(select(LineItem).where(LineItem.id == item_id))
    return result.scalar_one()


@router.delete("/{estimate_id}/line-items/{item_id}", status_code=204)
async def delete_line_item(
    estimate_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await load_estimate(estimate_id, current_user, db)
    result = await db.execute(
        select(LineItem).join(Estimate).where(
            LineItem.id == item_id, LineItem.estimate_id == estimate_id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")
    await db.delete(item)
    await db.flush()
    await db.commit()
    est = await load_estimate(estimate_id, current_user, db)
    recalc_totals(est)
    touch(est, current_user)
    await db.commit()


@router.post("/{estimate_id}/line-items/reorder", status_code=204)
async def reorder_line_items(
    estimate_id: uuid.UUID,
    data: ReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    est = await load_estimate(estimate_id, current_user, db)
    all_items = list(est.line_items)
    for zone in est.zones:
        all_items.extend(zone.line_items)
    id_to_item = {i.id: i for i in all_items}
    for idx, item_id in enumerate(data.ordered_ids):
        if item_id in id_to_item:
            id_to_item[item_id].sort_order = idx
    touch(est, current_user)
    await db.commit()
