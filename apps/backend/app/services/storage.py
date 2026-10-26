import os
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException
from app.core.config import settings

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/webm", "audio/ogg", "audio/mp4", "video/webm"}

async def save_upload(file: UploadFile, subdir: str) -> str:
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(413, "File too large (max 20MB)")

    ext = os.path.splitext(file.filename or "")[1] or ".bin"
    filename = f"{uuid.uuid4()}{ext}"
    rel_path = os.path.join(subdir, filename)
    full_path = os.path.join(settings.STORAGE_PATH, rel_path)

    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    async with aiofiles.open(full_path, "wb") as f:
        await f.write(content)

    return rel_path

def delete_file(rel_path: str):
    full_path = os.path.join(settings.STORAGE_PATH, rel_path)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except Exception:
        pass

def get_full_path(rel_path: str) -> str:
    return os.path.join(settings.STORAGE_PATH, rel_path)
