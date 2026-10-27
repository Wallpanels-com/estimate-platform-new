from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
import uuid

from app.core.database import get_db
from app.models.user import User
from app.models.estimate import Estimate, EstimateZone, LineItem, EstimateImage
from app.schemas.estimate import ZoneCreate, ZoneUpdate, ZoneOut
from app.api.deps import get_current_user
from app.api.v1.estimates import recalc_totals, load_estimate, touch
from app.core.estimate_routes import EstimateRoute

router = APIRouter(prefix="/estimates/{estimate_id}/zones", tags=["zones"], route_class=EstimateRoute)


async def load_zone(estimate_id: uuid.UUID, zone_id: uuid.UUID, user: User, db: AsyncSession) -> EstimateZone:
    await load_estimate(estimate_id, user, db)
    result = await db.execute(
        select(EstimateZone)
        .options(selectinload(EstimateZone.line_items), selectinload(EstimateZone.images))
        .join(Estimate)
        .where(EstimateZone.id == zone_id, EstimateZone.estimate_id == estimate_id)
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone


@router.get("", response_model=List[ZoneOut])
async def list_zones(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    est = await load_estimate(estimate_id, current_user, db)
    return est.zones


@router.post("", response_model=ZoneOut, status_code=201)
async def create_zone(
    estimate_id: uuid.UUID,
    data: ZoneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    est = await load_estimate(estimate_id, current_user, db)
    zone = EstimateZone(estimate_id=est.id, **data.model_dump())
    if data.sort_order == 0:
        zone.sort_order = len(est.zones)
    db.add(zone)
    touch(est, current_user)
    await db.flush()
    await db.commit()
    return await load_zone(estimate_id, zone.id, current_user, db)


@router.post("/{zone_id}/duplicate", response_model=ZoneOut, status_code=201)
async def duplicate_zone(
    estimate_id: uuid.UUID,
    zone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    src = await load_zone(estimate_id, zone_id, current_user, db)
    est = await load_estimate(estimate_id, current_user, db)

    new_zone = EstimateZone(
        estimate_id=estimate_id,
        sort_order=len(est.zones),  # append after last zone
        zone_type=src.zone_type,
        label=f"{src.label or 'Zone'} (copy)",
        room_name=src.room_name,
        wall_name=src.wall_name,
        wall_width_ft=src.wall_width_ft,
        wall_height_ft=src.wall_height_ft,
        square_footage=src.square_footage,
        linear_footage=src.linear_footage,
        notes=src.notes,
    )
    db.add(new_zone)
    await db.flush()

    for item in sorted(src.line_items, key=lambda i: i.sort_order):
        db.add(LineItem(
            estimate_id=estimate_id,
            zone_id=new_zone.id,
            section=item.section,
            sort_order=item.sort_order,
            name=item.name,
            description=item.description,
            calc_type=item.calc_type,
            quantity=item.quantity,
            unit=item.unit,
            unit_price=item.unit_price,
            total_price=item.total_price,
            original_unit_price=item.original_unit_price,
            is_tbd=item.is_tbd,
        ))

    from app.services.estimate_branches import image_copy
    for image in src.images:
        db.add(EstimateImage(estimate_id=estimate_id, zone_id=new_zone.id,
                            slot=image.slot, original_name=image.original_name,
                            file_path=image_copy(image.file_path, estimate_id, new_zone.id)))
    layout = dict(est.pdf_layout or {})
    choices = dict(layout.get('final_zone_photos', {}))
    if str(src.id) in choices:
        choices[str(new_zone.id)] = choices[str(src.id)]
        layout['final_zone_photos'] = choices
        est.pdf_layout = layout
    touch(est, current_user)
    await db.flush()
    est = await load_estimate(estimate_id, current_user, db)
    recalc_totals(est)
    await db.commit()
    return await load_zone(estimate_id, new_zone.id, current_user, db)


@router.post("/reorder", status_code=200)
async def reorder_zones(
    estimate_id: uuid.UUID,
    zone_ids: List[uuid.UUID],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    est = await load_estimate(estimate_id, current_user, db)
    id_to_zone = {z.id: z for z in est.zones}
    for idx, zid in enumerate(zone_ids):
        if zid in id_to_zone:
            id_to_zone[zid].sort_order = idx
    touch(est, current_user)
    await db.commit()
    return {"ok": True}


@router.patch("/{zone_id}", response_model=ZoneOut)
async def update_zone(
    estimate_id: uuid.UUID,
    zone_id: uuid.UUID,
    data: ZoneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    zone = await load_zone(estimate_id, zone_id, current_user, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(zone, field, value)
    est = await load_estimate(estimate_id, current_user, db)
    touch(est, current_user)
    await db.flush()
    await db.commit()
    return await load_zone(estimate_id, zone_id, current_user, db)


@router.delete("/{zone_id}", status_code=204)
async def delete_zone(
    estimate_id: uuid.UUID,
    zone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    zone = await load_zone(estimate_id, zone_id, current_user, db)
    await db.delete(zone)
    await db.flush()
    est = await load_estimate(estimate_id, current_user, db)
    recalc_totals(est)
    touch(est, current_user)
    await db.commit()
