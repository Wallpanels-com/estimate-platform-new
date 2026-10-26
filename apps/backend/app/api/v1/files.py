from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid, os, aiofiles

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.estimate import Estimate, EstimateZone, EstimateImage
from app.schemas.estimate import ImageOut
from app.api.deps import get_current_user
from app.api.v1.estimates import load_estimate, touch

router = APIRouter(prefix="/estimates/{estimate_id}/zones/{zone_id}", tags=["files"])

ALLOWED_IMG = {"image/jpeg", "image/png", "image/webp"}


async def verify_zone(estimate_id: uuid.UUID, zone_id: uuid.UUID, user: User, db: AsyncSession):
    await load_estimate(estimate_id, user, db)
    result = await db.execute(
        select(EstimateZone).join(Estimate).where(
            EstimateZone.id == zone_id, EstimateZone.estimate_id == estimate_id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Zone not found")


@router.post("/images/{slot}", response_model=ImageOut)
async def upload_image(
    estimate_id: uuid.UUID,
    zone_id: uuid.UUID,
    slot: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if slot < 1 or slot > 4:
        raise HTTPException(status_code=400, detail="Slot must be 1-4")
    if file.content_type not in ALLOWED_IMG:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG/WebP allowed")

    await verify_zone(estimate_id, zone_id, current_user, db)

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

    existing = await db.execute(
        select(EstimateImage).where(EstimateImage.zone_id == zone_id, EstimateImage.slot == slot)
    )
    for img in existing.scalars().all():
        try:
            os.remove(img.file_path)
        except FileNotFoundError:
            pass
        await db.delete(img)

    storage_dir = os.path.join(settings.STORAGE_PATH, "images", str(estimate_id), str(zone_id))
    os.makedirs(storage_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "img.jpg")[1] or ".jpg"
    filename = f"slot{slot}_{uuid.uuid4()}{ext}"
    file_path = os.path.join(storage_dir, filename)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    img = EstimateImage(estimate_id=estimate_id, zone_id=zone_id, slot=slot, file_path=file_path, original_name=file.filename)
    db.add(img)
    await db.flush()
    est = await load_estimate(estimate_id, current_user, db)
    touch(est, current_user)
    await db.commit()
    return img


@router.delete("/images/{slot}", status_code=204)
async def delete_image(
    estimate_id: uuid.UUID,
    zone_id: uuid.UUID,
    slot: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await verify_zone(estimate_id, zone_id, current_user, db)
    imgs = await db.execute(
        select(EstimateImage).where(EstimateImage.zone_id == zone_id, EstimateImage.slot == slot)
    )
    for img in imgs.scalars().all():
        try:
            os.remove(img.file_path)
        except FileNotFoundError:
            pass
        await db.delete(img)
    est = await load_estimate(estimate_id, current_user, db)
    touch(est, current_user)
    await db.commit()