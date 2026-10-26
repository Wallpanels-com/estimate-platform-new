from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional
import uuid, os, aiofiles

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.estimate import VoiceFile, Estimate, EstimateZone, LineItem
from app.services.ai_extraction import transcribe_audio, extract_estimate_data
from app.services.rule_engine import calc_zone
from app.services.pricing_config import get_pricing_config
from app.api.deps import get_current_user
from app.api.v1.estimates import touch

router = APIRouter(prefix="/voice", tags=["voice"])


class ExtractRequest(BaseModel):
    text: str
    estimate_id: uuid.UUID
    zone_id: uuid.UUID


@router.post("/transcribe")
async def transcribe(
    estimate_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Estimate).where(Estimate.id == estimate_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Estimate not found")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

    storage_dir = os.path.join(settings.STORAGE_PATH, "voice", str(estimate_id))
    os.makedirs(storage_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}{os.path.splitext(file.filename or 'audio.webm')[1]}"
    file_path = os.path.join(storage_dir, filename)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    transcript = await transcribe_audio(content, file.filename or "audio.webm")

    vf = VoiceFile(estimate_id=estimate_id, file_path=file_path, transcript=transcript)
    db.add(vf)
    await db.flush()
    await db.commit()

    return {"transcript": transcript, "voice_file_id": str(vf.id)}


@router.post("/extract")
async def extract(
    body: ExtractRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Analyze text for ONE zone, run the Rule Engine, and persist:
    - zone fields (room_name, wall_name, dimensions)
    - calculated line items (replacing any previous ones for this zone)
    - estimate-level fields (title, client, project, prepared_by, date, notes) if provided
    """
    if not body.text:
        raise HTTPException(status_code=400, detail="No text provided")

    # Verify ownership
    result = await db.execute(
        select(EstimateZone)
        .options(selectinload(EstimateZone.line_items))
        .join(Estimate)
        .where(EstimateZone.id == body.zone_id, EstimateZone.estimate_id == body.estimate_id)
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    est_result = await db.execute(select(Estimate).where(Estimate.id == body.estimate_id))
    estimate = est_result.scalar_one()

    data = await extract_estimate_data(body.text)

    # Take the first detected zone (single-zone extraction)
    zones = data.get("zones", [])
    ai_zone = zones[0] if zones else {}

    # Determine SF from dims if not given
    sf = ai_zone.get("square_footage") or data.get("square_footage")
    w = ai_zone.get("wall_width_ft") or data.get("wall_width_ft")
    h = ai_zone.get("wall_height_ft") or data.get("wall_height_ft")
    if not sf and w and h:
        sf = w * h

    # Update zone fields
    zone.zone_type = ai_zone.get("zone_type") or zone.zone_type
    if ai_zone.get("label"):
        zone.label = ai_zone["label"]
    elif data.get("room_name") or data.get("wall_name"):
        zone.label = data.get("wall_name") or data.get("room_name")
    zone.room_name = data.get("room_name") or zone.room_name
    zone.wall_name = data.get("wall_name") or zone.wall_name
    zone.wall_width_ft = w or zone.wall_width_ft
    zone.wall_height_ft = h or zone.wall_height_ft
    zone.square_footage = sf or zone.square_footage
    zone.linear_footage = ai_zone.get("linear_footage") or zone.linear_footage
    zone.notes = data.get("notes") or zone.notes

    # Update estimate-level (shared) fields
    if data.get("title"):
        estimate.title = data["title"]
    if data.get("client_name"):
        estimate.client_name = data["client_name"]
    if data.get("description"):
        estimate.description = data["description"]

    # Remove old line items for this zone, then calculate new ones
    for old_item in list(zone.line_items):
        await db.delete(old_item)
    await db.flush()

    zone_for_calc = {
        "zone_type": zone.zone_type,
        "square_footage": float(zone.square_footage) if zone.square_footage else None,
        "linear_footage": float(zone.linear_footage) if zone.linear_footage else None,
        "addons_sf": ai_zone.get("addons_sf", []),
        "addons_fixed": ai_zone.get("addons_fixed", []),
        "addons_lf": ai_zone.get("addons_lf", []),
        "budget": ai_zone.get("budget", False),
        "height": ai_zone.get("height"),
        "glass_doors": ai_zone.get("glass_doors", []),
        "panel_name": ai_zone.get("panel_name"),
        "panel_color": ai_zone.get("panel_color"),
        "panel_coverage_pct": ai_zone.get("panel_coverage_pct"),
    }
    pricing_config = await get_pricing_config(db)
    calc_result = calc_zone(zone_for_calc, config=pricing_config)

    for idx, item in enumerate(calc_result.get("line_items", [])):
        db.add(LineItem(
            estimate_id=body.estimate_id,
            zone_id=zone.id,
            section=item["section"],
            sort_order=idx,
            name=item["name"],
            description=item.get("description"),
            calc_type=item["calc_type"],
            quantity=item.get("quantity"),
            unit=item.get("unit"),
            unit_price=item.get("unit_price"),
            original_unit_price=item.get("unit_price"),  # snapshot at creation
            total_price=item["total_price"],
        ))

    touch(estimate, current_user)
    await db.flush()
    await db.commit()

    return {
        "zone_id": str(zone.id),
        "extracted": data,
        "zone": {
            "label": zone.label,
            "zone_type": zone.zone_type,
            "room_name": zone.room_name,
            "wall_name": zone.wall_name,
            "square_footage": float(zone.square_footage) if zone.square_footage else None,
            "linear_footage": float(zone.linear_footage) if zone.linear_footage else None,
        },
        "line_items_count": len(calc_result.get("line_items", [])),
    }
