from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rule_engine import calc_wall, calc_cabinet, calc_mirror, get_pricing_schema
from app.services.pricing_config import save_pricing_config, reset_pricing_config, DEFAULT_PRICING_CONFIG
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.pricebook_service import legacy_config, revision, save_legacy
from app.services.calculator_registry import calculate, definitions
from app.services.managed_rates import pricing_schema as managed_schema, get_config as get_pricing_config, with_managed_rates

router = APIRouter(prefix="/pricing", tags=["pricing"])


class FixedAddon(BaseModel):
    key: str
    qty: int = 1


class WallCalcRequest(BaseModel):
    square_footage: float
    base_rate_key: str | None = None
    addons_sf: List[str] = []
    addons_fixed: List[Union[str, FixedAddon]] = []
    panel_name: Optional[str] = None
    panel_color: Optional[str] = None
    panel_coverage_pct: Optional[float] = None


class CabinetCalcRequest(BaseModel):
    linear_footage: float
    budget: bool = False
    cabinet_type: Optional[str] = None
    addons_lf: List[str] = []
    glass_doors: List[dict] = []


class MirrorCalcRequest(BaseModel):
    square_footage: float
    mirror_type: str | None = None


@router.get("/schema")
async def pricing_schema(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = await get_pricing_config(db)
    return managed_schema(config)


@router.post("/calc/wall")
async def calculate_wall(
    data: WallCalcRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = await get_pricing_config(db)
    addons_fixed = [a.model_dump() if isinstance(a, FixedAddon) else a for a in data.addons_fixed]
    return calculate("wall", config, square_footage=data.square_footage, base_rate_key=data.base_rate_key, addons_sf=data.addons_sf, addons_fixed=addons_fixed,
        panel_name=data.panel_name, panel_color=data.panel_color,
        panel_coverage_pct=data.panel_coverage_pct,
    )


@router.post("/calc/cabinet")
async def calculate_cabinet(
    data: CabinetCalcRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = await get_pricing_config(db)
    return calculate("cabinet", config, linear_footage=data.linear_footage, budget=data.budget, cabinet_type=data.cabinet_type, addons_lf=data.addons_lf, glass_doors=data.glass_doors)


@router.post("/calc/mirror")
async def calculate_mirror(
    data: MirrorCalcRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = await get_pricing_config(db)
    return calculate("mirror", config, square_footage=data.square_footage, mirror_type=data.mirror_type)


# ─── PRICING CONFIG MANAGEMENT (Rule Engine editor) ───────────

class PricingConfigUpdate(BaseModel):
    config: dict
    expected_revision: str | None = None


def user_display_name(user: User) -> str:
    return user.name or user.email


@router.get("/config")
async def get_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the active pricing config plus whether it's the built-in default."""
    config = await get_pricing_config(db)
    is_default = (legacy_config(config) == with_managed_rates(DEFAULT_PRICING_CONFIG))
    return {"config": config, "is_default": is_default, "defaults": DEFAULT_PRICING_CONFIG, "revision": revision(config)}


@router.put("/config")
async def update_config(
    data: PricingConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await save_legacy(db, data.config, user_display_name(current_user), data.expected_revision)


@router.post("/config/reset")
async def reset_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await save_legacy(db, {}, user_display_name(current_user), reset=True)


@router.get("/quick-config")
async def get_quick_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the Quick Estimate room templates and pricing config."""
    config = await get_pricing_config(db)
    return {
        "quick_estimate": config.get("quick_estimate", DEFAULT_PRICING_CONFIG["quick_estimate"]),
        "cabinet_types": config.get("cabinet", {}).get("types", {}),
    }

@router.get("/calculators")
async def calculator_definitions(current_user: User = Depends(get_current_user)):
    return {"calculators": definitions()}
