"""Shared history, authenticated media and immutable issued exports."""
import hashlib
import tempfile
import uuid
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool
from app.api.deps import get_current_user
from app.api.v1.estimates import load_estimate
from app.api.v1.pdf import _render_final
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.estimate import Estimate, EstimateImage
from app.models.governance import AuditEvent, DocumentVersion
from app.schemas.estimate import EstimateOut
from app.services.pre_estimate_service import generate_pre_estimate
from app.services.passport_service import generate_passport
from app.services.estimate_branches import synchronize

router = APIRouter(tags=["history-and-documents"])


@router.get("/media/{image_id}")
async def image(image_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    record = await db.get(EstimateImage, image_id)
    if not record:
        raise HTTPException(404, "Photo not found.")
    root = Path(settings.STORAGE_PATH).resolve()
    path = Path(record.file_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "Photo file is unavailable.")
    return FileResponse(path, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


def history_row(row):
    return {"id": str(row.id), "actor_name": row.actor_name, "entity": row.entity, "entity_id": row.entity_id,
            "action": row.action, "changes": row.changes, "created_at": row.created_at}


@router.get("/estimates/{estimate_id}/history")
async def estimate_history(estimate_id: uuid.UUID, limit: int = 100, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    est = await load_estimate(estimate_id, user, db)
    root = est.source_estimate_id or est.id
    ids = (await db.execute(select(Estimate.id).where((Estimate.id == root) | (Estimate.source_estimate_id == root)))).scalars().all()
    rows = (await db.execute(select(AuditEvent).where(AuditEvent.estimate_id.in_(ids)).order_by(desc(AuditEvent.created_at), desc(AuditEvent.id)).limit(min(max(limit, 1), 500)))).scalars().all()
    return [history_row(row) for row in rows]


@router.get("/audit")
async def audit_history(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(200))).scalars().all()
    return [history_row(row) for row in rows]


def document_row(row):
    return {"id": str(row.id), "version": row.version, "kind": row.kind, "label": row.label,
            "actor_name": row.actor_name, "sha256": row.sha256, "created_at": row.created_at}


@router.get("/estimates/{estimate_id}/documents")
async def document_list(estimate_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await load_estimate(estimate_id, user, db)
    rows = (await db.execute(select(DocumentVersion).where(DocumentVersion.estimate_id == estimate_id).order_by(desc(DocumentVersion.created_at)))).scalars().all()
    return [document_row(row) for row in rows]


class IssueDocument(BaseModel):
    kind: Literal["pdf", "xlsx"]
    label: str = Field(min_length=1, max_length=120)


@router.post("/estimates/{estimate_id}/documents", status_code=201)
async def issue_document(estimate_id: uuid.UUID, data: IssueDocument, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    est = await load_estimate(estimate_id, user, db)
    if est.deleted_at:
        raise HTTPException(409, "Restore this estimate before issuing a document.")
    if est.source_estimate_id:
        est = await synchronize(db, est)
        await db.flush()
    snapshot = EstimateOut.model_validate(est).model_dump(mode="json")
    version = (await db.execute(select(func.max(DocumentVersion.version)).where(DocumentVersion.estimate_id == est.id, DocumentVersion.kind == data.kind))).scalar() or 0
    ident = uuid.uuid4()
    directory = Path(settings.STORAGE_PATH).resolve() / "issued" / str(est.id)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{ident}.{data.kind}"
    try:
        with tempfile.TemporaryDirectory(dir=directory) as work:
            if data.kind == "xlsx":
                generated = Path(work) / "passport.xlsx"
                await run_in_threadpool(generate_passport, est, generated)
            elif est.type == "pre":
                generated = Path(work) / "pre.pdf"
                await run_in_threadpool(generate_pre_estimate, est, generated)
            else:
                generated = Path(await _render_final(est, work))
            # Exclusive write: issued bytes never overwrite another version.
            with target.open("xb") as stream:
                stream.write(generated.read_bytes())
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        record = DocumentVersion(id=ident, estimate_id=est.id, version=version + 1, kind=data.kind,
            label=data.label, actor_name=user.name or user.email, file_path=str(target), sha256=digest, snapshot=snapshot)
        db.add(record)
        await db.commit()
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return document_row(record)


@router.get("/documents/{document_id}")
async def download_document(document_id: uuid.UUID, download: bool = False, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    record = await db.get(DocumentVersion, document_id)
    if not record:
        raise HTTPException(404, "Document not found.")
    path = Path(record.file_path).resolve()
    if not path.is_relative_to(Path(settings.STORAGE_PATH).resolve()) or not path.is_file():
        raise HTTPException(503, "Saved document file is unavailable. Restore it from backup.")
    if hashlib.sha256(path.read_bytes()).hexdigest() != record.sha256:
        raise HTTPException(503, "Saved document integrity check failed.")
    media = "application/pdf" if record.kind == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(path, media_type=media, filename=f"Estimate-v{record.version}.{record.kind}",
        content_disposition_type="attachment" if download else "inline", headers={"Cache-Control": "private, no-store"})
