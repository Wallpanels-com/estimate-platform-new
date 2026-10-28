from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
import tempfile
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid, os, re

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.estimate import Estimate, EstimateZone, PdfFile
from app.services.pdf_service import generate_pdf
from app.services.final_estimate_service import generate_final_estimate, FinalEstimatePdfError
from app.services.passport_service import generate_passport
from app.services.pre_estimate_service import generate_pre_estimate, design_version
from app.api.deps import get_current_user
from app.services.estimate_branches import synchronize, switch_mode
from app.services.final_pricing import quote
from app.services.final_zone_layout import photos as validate_zone_photos
from app.services.final_zone_photos import selected_slot, PHOTO_REQUIRED
from app.api.v1.estimates import load_estimate

router = APIRouter(prefix="/pdf", tags=["pdf"])


class _FinalEstimateView:
    """Select the existing Final renderer without assigning to an ORM model."""

    type = "final"

    def __init__(self, estimate):
        self._estimate = estimate

    def __getattr__(self, name):
        return getattr(self._estimate, name)


async def _render_final(estimate, output_dir):
    try:
        return await run_in_threadpool(generate_final_estimate, _FinalEstimateView(estimate), output_dir)
    except FinalEstimatePdfError as error:
        raise HTTPException(status_code=422 if str(error) == PHOTO_REQUIRED else 503, detail=str(error)) from error


def _sanitize(raw: str, fallback: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "", raw.strip())
    return re.sub(r"\s+", " ", name)[:120].strip() or fallback


def _safe_name(estimate: Estimate) -> str:
    """Filesystem-safe download name based on the estimate title (as shown on the site)."""
    return _sanitize(estimate.title or estimate.room_name or "estimate", "estimate")


def _passport_name(estimate: Estimate) -> str:
    """Passport download name: 'Project passport - Wallpanels - <Client>'."""
    client = _sanitize(estimate.client_name or estimate.title or estimate.room_name or "Client", "Client")
    return f"Project passport - Wallpanels - {client}"


@router.post("/{estimate_id}/generate")
async def generate(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Estimate)
        .options(
            selectinload(Estimate.line_items),
            selectinload(Estimate.images),
            selectinload(Estimate.zones).selectinload(EstimateZone.line_items),
            selectinload(Estimate.zones).selectinload(EstimateZone.images),
        )
        .where(Estimate.id == estimate_id)
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    if getattr(estimate, 'source_estimate_id', None):
        estimate = await synchronize(db, estimate)
        await db.commit()
    # Compatibility endpoint: validate a fresh render without retaining a file
    # or creating a persistent PdfFile record. Downloads always render current data.
    mode = 'final' if estimate.type == 'final' else 'pre'
    with tempfile.TemporaryDirectory(prefix="wallpanels-validate-") as output_dir:
        if mode == 'final':
            await _render_final(estimate, output_dir)
        else:
            await run_in_threadpool(generate_pre_estimate, estimate, Path(output_dir) / 'pre-estimate.pdf')
    endpoint = f"/api/v1/pdf/{estimate_id}/{mode}-estimate"
    return {"status": "ready", "preview_url": endpoint, "download_url": endpoint + "?download=true"}


@router.get("/{estimate_id}/download")
async def download(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Estimate).where(Estimate.id == estimate_id)
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    if estimate.type == 'final':
        # Legacy download links must not serve an older PDF without corporate slides.
        return await final_estimate(estimate_id, True, db, current_user)
    return await pre_estimate(estimate_id, True, db, current_user)


@router.get("/{estimate_id}/passport")
async def passport(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export the estimate as the 'Project Passport' spreadsheet (XLSX)."""
    result = await db.execute(
        select(Estimate)
        .options(selectinload(Estimate.zones).selectinload(EstimateZone.line_items),
                 selectinload(Estimate.line_items))
        .where(Estimate.id == estimate_id)
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    if getattr(estimate, "source_estimate_id", None):
        estimate = await load_estimate(estimate_id, current_user, db)
        estimate = await synchronize(db, estimate)
        await db.commit()

    output_dir = os.path.join(settings.STORAGE_PATH, "passports", str(estimate_id))
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"passport-{uuid.uuid4()}.xlsx")
    try:
        await run_in_threadpool(generate_passport, estimate, output_path)
    except Exception:
        Path(output_path).unlink(missing_ok=True)
        raise

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{_passport_name(estimate)}.xlsx",
        background=BackgroundTask(lambda: Path(output_path).unlink(missing_ok=True)),
    )

@router.get("/{estimate_id}/pre-estimate")
async def pre_estimate(
    estimate_id: uuid.UUID,
    download: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Independent proposal preview; the saved type, prices and metadata are read-only."""
    result = await db.execute(
        select(Estimate).options(
            selectinload(Estimate.images),
            selectinload(Estimate.zones).selectinload(EstimateZone.line_items),
            selectinload(Estimate.zones).selectinload(EstimateZone.images),
            selectinload(Estimate.line_items),
        ).where(Estimate.id == estimate_id, Estimate.deleted_at.is_(None))
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(404, "Estimate not found")
    temporary = tempfile.TemporaryDirectory(prefix="wallpanels-proposal-")
    try:
        path = await run_in_threadpool(generate_pre_estimate, estimate, Path(temporary.name) / "proposal.pdf")
    except FinalEstimatePdfError as error:
        temporary.cleanup()
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception:
        temporary.cleanup()
        raise
    client = _sanitize(estimate.client_name or estimate.title or "Project", "Project")
    return FileResponse(
        path, media_type="application/pdf",
        filename=f"Pre-Estimate - Wallpanels - {client}.pdf",
        content_disposition_type="attachment" if download else "inline",
        headers={"Cache-Control": "no-store", "X-Pre-Estimate-Design": design_version()},
        background=BackgroundTask(temporary.cleanup),
    )


@router.get("/{estimate_id}/final-check")
async def final_check(
    estimate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read-only export diagnostics; does not recalculate or change saved prices."""
    result = await db.execute(
        select(Estimate).options(
            selectinload(Estimate.zones).selectinload(EstimateZone.line_items),
            selectinload(Estimate.zones).selectinload(EstimateZone.images),
            selectinload(Estimate.line_items), selectinload(Estimate.images),
        ).where(Estimate.id == estimate_id, Estimate.deleted_at.is_(None))
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(404, "Estimate not found")
    if getattr(estimate, 'source_estimate_id', None):
        estimate = await synchronize(db, estimate)
        await db.commit()
    checks = quote(estimate)
    missing_photo_zones = []
    for zone in estimate.zones:
        if not zone.images:
            missing_photo_zones.append(zone.label)
        try:
            await run_in_threadpool(validate_zone_photos, zone, selected_slot(estimate, zone))
        except ValueError as error:
            checks.errors.append(str(error))
    result = {"warnings": checks.warnings, "errors": list(dict.fromkeys(checks.errors))}
    if missing_photo_zones:
        result["missing_photo_zones"] = missing_photo_zones
    return result


@router.get("/{estimate_id}/final-estimate")
async def final_estimate(
    estimate_id: uuid.UUID,
    download: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read-only Final preview/download: client pages, then exactly 13 company pages."""
    result = await db.execute(
        select(Estimate).options(
            selectinload(Estimate.images),
            selectinload(Estimate.zones).selectinload(EstimateZone.line_items),
            selectinload(Estimate.zones).selectinload(EstimateZone.images),
            selectinload(Estimate.line_items),
        ).where(Estimate.id == estimate_id, Estimate.deleted_at.is_(None))
    )
    estimate = result.scalar_one_or_none()
    if not estimate:
        raise HTTPException(404, "Estimate not found")
    if getattr(estimate, 'source_estimate_id', None):
        estimate = await synchronize(db, estimate)
        await db.commit()
    temporary = tempfile.TemporaryDirectory(prefix="wallpanels-final-")
    try:
        path = await _render_final(estimate, temporary.name)
    except Exception:
        temporary.cleanup()
        raise
    client = _sanitize(estimate.client_name or estimate.title or "Project", "Project")
    return FileResponse(
        path, media_type="application/pdf",
        filename=f"Final Estimate - Wallpanels - {client}.pdf",
        content_disposition_type="attachment" if download else "inline",
        headers={"Cache-Control": "no-store", "X-WallPanels-Company-Pages": "13"},
        background=BackgroundTask(temporary.cleanup),
    )
