from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sqlalchemy import text
import os

from app.core.config import settings
from app.core.schema_version import current_revision
from app.core.database import engine, Base, AsyncSessionLocal
from app.api.v1 import auth, estimates, voice, files, pdf, pricing, zones, pricebook, users, governance, backups
from app.services import audit  # register transaction-level audit hooks




@asynccontextmanager
async def lifespan(app: FastAPI):
    for d in ["images", "voice", "pdfs", "passports", "issued"]:
        os.makedirs(os.path.join(settings.STORAGE_PATH, d), exist_ok=True)

    if settings.AUTO_MIGRATE:
        raise RuntimeError("Startup schema changes are disabled. Run the approved Alembic migration explicitly.")

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        if result.scalar_one_or_none() != current_revision():
            raise RuntimeError("Database migrations are required. Run the approved Alembic upgrade before starting the application.")

    import asyncio
    from app.services.backups import daily_backups
    backup_task = asyncio.create_task(daily_backups()) if settings.BACKUP_ENABLED else None
    try:
        yield
    finally:
        if backup_task:
            backup_task.cancel()
            try:
                await backup_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Estimate Platform API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Client uploads are served only by authenticated routes in governance.py.

app.include_router(auth.router, prefix="/api/v1")
app.include_router(estimates.router, prefix="/api/v1")
app.include_router(zones.router, prefix="/api/v1")
app.include_router(voice.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(pdf.router, prefix="/api/v1")
app.include_router(pricing.router, prefix="/api/v1")
app.include_router(pricebook.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(governance.router, prefix="/api/v1")
app.include_router(backups.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}

# Optional single-origin serving for a pre-built SPA. Vite is used in development.
if settings.FRONTEND_DIST:
    from pathlib import Path
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    frontend_dist = Path(settings.FRONTEND_DIST).resolve()
    if (frontend_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend_assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str):
        if path.split("/", 1)[0] in {"api", "storage", "docs", "redoc", "openapi.json"}:
            raise HTTPException(404)
        requested = (frontend_dist / path).resolve()
        if requested.is_relative_to(frontend_dist) and requested.is_file():
            return FileResponse(requested)
        index = frontend_dist / "index.html"
        if not index.exists():
            raise HTTPException(404, "Frontend build is unavailable. Run npm run build.")
        return FileResponse(index)
