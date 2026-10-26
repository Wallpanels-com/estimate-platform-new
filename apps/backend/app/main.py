from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sqlalchemy import text
import os

from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal
from app.api.v1 import auth, estimates, voice, files, pdf, pricing, zones, pricebook


MIGRATION_SQL = [
    "ALTER TABLE estimates ADD COLUMN IF NOT EXISTS source_estimate_id UUID REFERENCES estimates(id) ON DELETE CASCADE",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_estimates_source_estimate_id ON estimates(source_estimate_id)",
    "ALTER TABLE estimates ADD COLUMN IF NOT EXISTS branch_state JSON",
    "ALTER TABLE estimates ADD COLUMN IF NOT EXISTS cover_image_id VARCHAR",
    """
    CREATE TABLE IF NOT EXISTS estimate_zones (
        id UUID PRIMARY KEY,
        estimate_id UUID NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
        sort_order INTEGER DEFAULT 0,
        zone_type VARCHAR DEFAULT 'wall',
        label VARCHAR DEFAULT 'Zone',
        room_name VARCHAR,
        wall_name VARCHAR,
        wall_width_ft NUMERIC(10,2),
        wall_height_ft NUMERIC(10,2),
        square_footage NUMERIC(10,2),
        linear_footage NUMERIC(10,2),
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    "ALTER TABLE line_items ADD COLUMN IF NOT EXISTS zone_id UUID REFERENCES estimate_zones(id) ON DELETE CASCADE",
    "ALTER TABLE estimate_images ADD COLUMN IF NOT EXISTS zone_id UUID REFERENCES estimate_zones(id) ON DELETE CASCADE",
    "CREATE INDEX IF NOT EXISTS ix_line_items_zone_id ON line_items(zone_id)",
    "CREATE INDEX IF NOT EXISTS ix_estimate_images_zone_id ON estimate_images(zone_id)",
    "CREATE INDEX IF NOT EXISTS ix_estimate_zones_estimate_id ON estimate_zones(estimate_id)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT false",
    "ALTER TABLE estimates ADD COLUMN IF NOT EXISTS created_by_name VARCHAR",
    "ALTER TABLE estimates ADD COLUMN IF NOT EXISTS updated_by_name VARCHAR",
    """
    UPDATE estimates e SET created_by_name = COALESCE(u.name, u.email)
    FROM users u WHERE e.user_id = u.id AND e.created_by_name IS NULL
    """,
    "UPDATE estimates SET updated_by_name = created_by_name WHERE updated_by_name IS NULL",
    "ALTER TABLE estimates ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS ix_estimates_deleted_at ON estimates (deleted_at)",
    "ALTER TABLE estimates ADD COLUMN IF NOT EXISTS markup_pct NUMERIC(6,2)",
    "ALTER TABLE estimates ADD COLUMN IF NOT EXISTS discount_pct NUMERIC(6,2)",
    "ALTER TABLE line_items ADD COLUMN IF NOT EXISTS original_unit_price NUMERIC(12,2)",
    "ALTER TABLE line_items ADD COLUMN IF NOT EXISTS is_tbd BOOLEAN DEFAULT FALSE",
    """
    CREATE TABLE IF NOT EXISTS pricing_config (
        id UUID PRIMARY KEY,
        config JSON NOT NULL,
        updated_by_name VARCHAR,
        updated_at TIMESTAMPTZ DEFAULT now()
    )
    """,
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    for d in ["images", "voice", "pdfs"]:
        os.makedirs(os.path.join(settings.STORAGE_PATH, d), exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Idempotent migrations for existing deployments
    async with AsyncSessionLocal() as session:
        for stmt in MIGRATION_SQL:
            await session.execute(text(stmt))
        await session.commit()

    yield


app = FastAPI(title="Estimate Platform API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_path = os.path.join(settings.STORAGE_PATH)
os.makedirs(static_path, exist_ok=True)
app.mount("/storage", StaticFiles(directory=static_path), name="storage")

app.include_router(auth.router, prefix="/api/v1")
app.include_router(estimates.router, prefix="/api/v1")
app.include_router(zones.router, prefix="/api/v1")
app.include_router(voice.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(pdf.router, prefix="/api/v1")
app.include_router(pricing.router, prefix="/api/v1")
app.include_router(pricebook.router, prefix="/api/v1")


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
