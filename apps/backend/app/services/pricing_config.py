"""
Editable pricing configuration for the Rule Engine.

The DEFAULT_PRICING_CONFIG below mirrors the original hardcoded values in
rule_engine.py. At runtime, get_pricing_config() returns the active config:
the single row from the pricing_config table if one exists, otherwise these
defaults. Saving via the API writes a JSON blob shaped exactly like this
dict, so the Rule Engine's calc functions can consume either one identically.

Shape:
{
  "wall": {
    "base_rates": {"large": 50, "medium": 55, "small": 60},
    "addons_sf": {"<key>": {"label": str, "price": number, "describable": bool}, ...},
    "addons_fixed": {"<key>": {"label": str, "price": number}, ...}
  },
  "cabinet": {
    "base_rate": 1000,
    "base_rate_budget": 900,
    "addons_lf": {"<key>": {"label": str, "price": number}, ...},
    "height_addons": {"<key>": {"label": str, "price": number}, ...},
    "glass_doors": {"<key>": {"label": str, "price": number}, ...}
  },
  "mirror": {
    "rate": 80,
    "minimum": 1000
  }
}

"describable" on a wall SF addon controls whether its label appears in the
generated line-item description (only "physical" features like LED should -
pricing-tier labels like "Premium material" stay hidden, per the existing
DESCRIBABLE_FEATURES set).
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.estimate import PricingConfig


DEFAULT_PRICING_CONFIG = {
    "wall": {
        "base_rates": {
            "large": 50,
            "medium": 55,
            "small": 60,
        },
        "addons_sf": {
            "led":                       {"label": "LED lighting",                    "price": 5,  "describable": True},
            "premium_material":          {"label": "Premium material",                "price": 5,  "describable": False},
            "very_premium_material":     {"label": "Very premium material",           "price": 10, "describable": False},
            "multidimensional":          {"label": "Multidimensional design",         "price": 5,  "describable": False},
            "highly_multidimensional":   {"label": "Highly multidimensional design",  "price": 10, "describable": False},
            "many_small_pieces":         {"label": "Many small pieces",               "price": 5,  "describable": False},
            "very_many_small_pieces":    {"label": "Very many small pieces",          "price": 10, "describable": False},
            "staircase":                 {"label": "Staircase installation",          "price": 5,  "describable": True},
            "recessed_lighting":         {"label": "Recessed lighting",               "price": 5,  "describable": True},
        },
        "addons_fixed": {
            "hidden_door":      {"label": "Hidden door",      "price": 2500},
            "tall_hidden_door": {"label": "Tall hidden door", "price": 3000},
        },
    },
    "cabinet": {
        "base_rate": 1000,
        "base_rate_budget": 900,
        # Cabinet types — each with its own base rate ($/LF)
        "types": {
            "kitchen_cabinetry": {"label": "Kitchen Cabinetry",     "base_rate": 1000},
            "kitchen_island":    {"label": "Kitchen Island",         "base_rate": 1200},
            "tv_stand":          {"label": "TV Stand",               "base_rate": 600},
            "night_stands":      {"label": "Night Stands",           "base_rate": 1400},
            "bar_cabinetry":     {"label": "Bar Cabinetry",          "base_rate": 1200},
            "entry_console":     {"label": "Entry Console",          "base_rate": 1400},
            "vanity":            {"label": "Vanity",                 "base_rate": 1200},
            "desk_budget":       {"label": "Desk (Budget)",          "base_rate": 800},
            "desk_highend":      {"label": "Desk (High-end)",        "base_rate": 1600},
            "wardrobe_closet":   {"label": "Wardrobe / Closet",      "base_rate": 950},
            "builtin_cabinetry": {"label": "Built-in Cabinetry",     "base_rate": 1200},
        },
        "addons_lf": {
            "wood_veneer":          {"label": "Wood veneer",            "price": 100, "describable": False},
            "slim_shaker":          {"label": "Slim shaker",            "price": 100, "describable": False},
            "plywood_construction": {"label": "Plywood construction",   "price": 100, "describable": False},
            "integrated_handles":   {"label": "Integrated handles",     "price": 100, "describable": False},
            "led_lighting":         {"label": "LED interior lighting",  "price": 100, "describable": True},
            "luxury_finish":        {"label": "Luxury finish",          "price": 100, "describable": False},
            "complex_design":       {"label": "Complex design",         "price": 100, "describable": False},
            "difficult_install":    {"label": "Difficult installation", "price": 100, "describable": False},
        },
        "glass_doors": {
            "standard": {"label": "Standard glass door", "price": 650},
            "large":    {"label": "Large glass door",    "price": 1250},
        },
    },
    "mirror": {
        "rate": 80,
        "minimum": 1000,
    },
    # ── Materials catalogue ──────────────────────────────────────────────────
    # Each entry defines how a material maps to a pricing tier (addon_sf key)
    # and what price adder it implies. The frontend combobox reads this list
    # and auto-applies the correct addons_sf when the user picks a material.
    # tier: "base" | "premium" | "very_premium"
    # addon_key: matches a key in wall.addons_sf (or null for base tier)
    "materials": {
        # Wood-based
        "flat_mdf":          {"label": "Flat MDF",              "group": "Wood-based",            "tier": "base",         "addon_key": None,                 "price_adder": 0},
        "flat_natural_wood": {"label": "Flat Natural Wood",     "group": "Wood-based",            "tier": "premium",      "addon_key": "premium_material",   "price_adder": 5},
        "wood_veneer":       {"label": "Wood Veneer",           "group": "Wood-based",            "tier": "very_premium", "addon_key": "very_premium_material","price_adder": 10},
        "bamboo_veneer":     {"label": "Bamboo Veneer",         "group": "Wood-based",            "tier": "very_premium", "addon_key": "very_premium_material","price_adder": 10},
        "slats_mdf":         {"label": "Slats MDF",             "group": "Wood-based",            "tier": "premium",      "addon_key": "premium_material",   "price_adder": 5},
        "slats_natural_wood":{"label": "Slats Natural Wood",    "group": "Wood-based",            "tier": "very_premium", "addon_key": "very_premium_material","price_adder": 10},
        # Engineered / Composite
        "pvc":               {"label": "PVC",                   "group": "Engineered / Composite","tier": "base",         "addon_key": None,                 "price_adder": 0},
        # Stone & Mineral
        "natural_stone":     {"label": "Natural Stone",         "group": "Stone & Mineral",       "tier": "very_premium", "addon_key": "very_premium_material","price_adder": 10},
        "porcelain_slab":    {"label": "Porcelain Slab",        "group": "Stone & Mineral",       "tier": "premium",      "addon_key": "premium_material",   "price_adder": 5},
        "gypsum_plaster":    {"label": "Gypsum / Plaster",      "group": "Stone & Mineral",       "tier": "base",         "addon_key": None,                 "price_adder": 0},
    },
    # ── Quick Estimate config ────────────────────────────────────────────────
    # Separate pricing for the Quick Estimate (room template) mode.
    # All prices here are editable via a dedicated settings page (future).
    # range_pct: ± percentage applied to all totals in Quick Estimate PDF.
    "quick_estimate": {
        "range_pct": 20,          # ±20% range on all totals
        "wall_rate": 80,          # $/SF for all wall panels
        "mirror_rate": 80,        # $/SF for mirrors
        "mirror_installation": {
            "rate_small": 95,     # $/SF when SF ≤ 20
            "rate_large": 80,     # $/SF when SF > 20
            "threshold_sf": 20,
        },
        "rooms": {
            "hallway": {
                "label": "Hallway / Entryway",
                "items": ["wall_panels", "led_lighting", "mirror", "entry_console", "electrical_work", "floor_protection"],
            },
            "living_room": {
                "label": "Living Room",
                "items": ["wall_panels", "led_lighting", "tv_stand", "electrical_work"],
                "options": ["fireplace", "buildout"],
            },
            "kitchen": {
                "label": "Kitchen",
                "items": ["kitchen_cabinets", "kitchen_island", "backsplash", "led_lighting", "countertop", "plumbing_services", "electrical_work", "floor_protection"],
                "options": ["budget_highend"],
            },
            "bedroom": {
                "label": "Bedroom",
                "items": ["wall_panels", "led_lighting", "night_stands", "electrical_work", "floor_protection"],
                "options": ["mirror", "wardrobe"],
            },
            "bathroom": {
                "label": "Bathroom",
                "items": ["wall_panels", "vanity", "mirror", "led_lighting", "plumbing_services", "electrical_work", "floor_protection"],
            },
            "home_office": {
                "label": "Home Office",
                "items": ["led_lighting", "electrical_work", "appliance_installation", "floor_protection"],
                "options": ["wall_panels", "cabinetry", "desk"],
            },
            "bar": {
                "label": "Bar",
                "items": ["bar_cabinetry", "wall_panels", "backsplash", "led_lighting", "countertop", "bottle_racks", "glass_doors", "plumbing_services", "electrical_work", "floor_protection"],
            },
            "gym_media": {
                "label": "Gym / Media Room",
                "items": ["wall_panels", "led_lighting", "electrical_work", "floor_protection"],
                "options": ["builtin_storage"],
            },
            "staircase": {
                "label": "Staircase / Landing",
                "items": ["wall_panels", "led_lighting", "electrical_work", "floor_protection"],
            },
        },
        "fixed_items": {
            "efireplace_unit":       {"label": "E-Fireplace Unit",              "price": 2200},
            "fireplace_installation":{"label": "Fireplace Installation",         "price": 1000},
            "bottle_racks":          {"label": "Bottle Racks",                  "price": 1500},
        },
        "buildout_tiers": [
            {"label": "Up to 12 ft",  "max_ft": 12,  "price": 2000},
            {"label": "12–18 ft",     "max_ft": 18,  "price": 4000},
            {"label": "18–24 ft",     "max_ft": 24,  "price": 5000},
            {"label": "24 ft+",       "max_ft": 9999,"price": 6000},
        ],
    },
    # Predefined service line items the user can add to any zone estimate.
    # default_price: 0 means manager fills in the price per project.
    # unit: "Fixed" | "SF" | "HR"
    "services": {
        "demolition":         {"label": "Demolition of existing walls/surfaces", "default_price": 0, "unit": "Fixed"},
        "garbage_removal":    {"label": "Garbage removal & haul-away",           "default_price": 0, "unit": "Fixed"},
        "surface_prep":       {"label": "Surface preparation",                   "default_price": 0, "unit": "Fixed"},
        "floor_protection":   {"label": "Floor & furniture protection",          "default_price": 0, "unit": "Fixed"},
        "masking_taping":     {"label": "Masking & taping",                     "default_price": 0, "unit": "Fixed"},
        "vent_relocation":    {"label": "Vent relocation",                       "default_price": 0, "unit": "Fixed"},
        "electrician":        {"label": "Electrician services",                  "default_price": 0, "unit": "Fixed"},
        "plumbing":           {"label": "Plumbing services",                     "default_price": 0, "unit": "Fixed"},
        "framing":            {"label": "Framing / blocking installation",       "default_price": 0, "unit": "Fixed"},
        "touch_up_painting":  {"label": "Touch-up painting",                    "default_price": 0, "unit": "Fixed"},
    },
    # Grouped list for the Color / Finish combobox. No pricing effect.
    "colors": [
        {"group": "Neutrals",     "options": ["White / Cream / Off-white", "Light grey / Medium grey / Dark grey / Charcoal", "Black / Near-black"]},
        {"group": "Warm tones",   "options": ["Warm white / Ivory", "Beige / Sand / Taupe", "Warm brown / Caramel / Cognac", "Terracotta / Clay"]},
        {"group": "Wood tones",   "options": ["Light wood (ash, birch, pine)", "Medium wood (oak, maple, walnut light)", "Dark wood (walnut dark, wenge, ebony)"]},
        {"group": "Stone tones",  "options": ["Cream marble veined", "Grey marble veined", "Black marble veined", "Travertine beige", "Onyx green / Onyx honey"]},
        {"group": "Accent",       "options": ["Navy / Deep blue", "Forest green / Sage", "Burgundy / Deep red", "Gold / Champagne", "Rose / Blush"]},
    ],
}


async def get_pricing_config(db: AsyncSession) -> dict:
    """Returns the active pricing config: DB row if present, else defaults."""
    result = await db.execute(select(PricingConfig).limit(1))
    row = result.scalars().first()
    if row and row.config:
        return row.config
    return DEFAULT_PRICING_CONFIG


async def save_pricing_config(db: AsyncSession, config: dict, updated_by_name: Optional[str]) -> PricingConfig:
    result = await db.execute(select(PricingConfig).limit(1))
    row = result.scalars().first()
    if row:
        row.config = config
        row.updated_by_name = updated_by_name
    else:
        row = PricingConfig(config=config, updated_by_name=updated_by_name)
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def reset_pricing_config(db: AsyncSession, updated_by_name: Optional[str]) -> PricingConfig:
    return await save_pricing_config(db, DEFAULT_PRICING_CONFIG, updated_by_name)