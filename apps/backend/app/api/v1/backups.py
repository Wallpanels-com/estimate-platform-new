"""Equal-User, authenticated backup operations; no live restore endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool
from app.api.deps import get_current_user
from app.core.config import settings
from app.services import backups

router = APIRouter(prefix="/operations/backups", tags=["backups"], dependencies=[Depends(get_current_user)])


@router.get("")
async def status():
    return {**backups.status(), "enabled": settings.BACKUP_ENABLED}


@router.post("", status_code=201)
async def create(verify: bool = False):
    try:
        return await run_in_threadpool(backups.create_backup, verify)
    except Exception:
        raise HTTPException(503, "Backup could not be completed. No existing data was changed; check backup storage and retry.") from None


@router.post("/remove-pdf-archives")
async def remove_pdf_archives():
    from app.services.pdf_retention import apply_policy
    try:
        return await run_in_threadpool(apply_policy)
    except Exception as error:
        import logging
        logging.getLogger(__name__).error("PDF policy cleanup failed (%s)", type(error).__name__)
        raise HTTPException(503, "PDF archive cleanup did not complete. Estimate data and photographs were not changed. Retry after any active backup completes.") from None
