"""
WallPanels Pricing Engine v1
Pure Python, no DB dependencies. Prices in USD.

Pricing model for walls:
- All "+$X/SF" multipliers (led, premium materials, multidimensional, mosaic,
  staircase, recessed lighting, etc.) are FOLDED into a single combined
  per-SF rate. They do NOT appear as separate line items.
- Only ONE line item is created for the panel install itself. Its name is
  the panel name/color if the user described one (e.g. "Calacatta Gold
  Marble Panels"), otherwise a generic "Wall panels — supply & install".
  The description lists the included features for transparency.
- Fixed-price add-ons (hidden door, etc.) remain separate line items.
- If the user described panels covering only part of the wall (coverage %),
  the billable SF = wall SF * coverage%. The full wall SF is still shown
  in the description for context.

All prices/labels come from a pricing config dict (see
app/services/pricing_config.py for the shape and defaults). Every calc_*
function accepts an optional `config` argument; if omitted, the hardcoded
DEFAULT_PRICING_CONFIG is used (useful for tests / non-DB contexts).
"""
from decimal import Decimal
from typing import List, Optional

from app.services.pricing_config import DEFAULT_PRICING_CONFIG


# Only these wall SF add-ons are "physical" features worth mentioning in the
# line item description — material/complexity tiers (premium_material,
# multidimensional, mosaic, etc.) are pricing-only and stay hidden. This is
# driven by the "describable" flag on each addon in the pricing config.


def wall_size_tier(sf: Decimal) -> str:
    if sf >= 250:
        return "large"
    elif sf >= 100:
        return "medium"
    return "small"


def calc_wall(
    square_footage: float,
    addons_sf: List[str] = None,
    addons_fixed: List = None,
    panel_name: Optional[str] = None,
    panel_color: Optional[str] = None,
    panel_coverage_pct: Optional[float] = None,
    config: Optional[dict] = None,
) -> dict:
    """
    addons_fixed: list of either strings (qty=1) or {"key": str, "qty": int}
    panel_name / panel_color: optional description of the panel material/finish.
        If provided, becomes the line item name (e.g. "Calacatta Gold Marble Panels").
    panel_coverage_pct: optional 0-100. If the panels only cover part of the wall
        (e.g. wainscoting, partial feature wall), the billable SF is reduced
        proportionally. The full wall SF is still shown for context.
    config: pricing config dict (see pricing_config.py). Defaults to DEFAULT_PRICING_CONFIG.
    """
    cfg = (config or DEFAULT_PRICING_CONFIG)["wall"]

    sf = Decimal(str(square_footage)) if square_footage else Decimal("0")
    addons_sf    = addons_sf or []
    addons_fixed = addons_fixed or []

    tier       = wall_size_tier(sf)
    base_rate  = Decimal(str(cfg["base_rates"][tier]))
    tier_label = {"large": "Large wall (250+ SF)", "medium": "Medium wall (100\u2013249 SF)", "small": "Small wall (<100 SF)"}[tier]

    # Fold all per-SF multipliers into one combined rate
    combined_rate = base_rate
    applied_labels = []
    addons_sf_cfg = cfg.get("addons_sf", {})
    for key in addons_sf:
        addon = addons_sf_cfg.get(key)
        if not addon:
            continue
        combined_rate += Decimal(str(addon["price"]))
        if addon.get("describable"):
            applied_labels.append(addon.get("label", key))

    # Effective billable SF (coverage)
    if panel_coverage_pct and 0 < panel_coverage_pct < 100:
        effective_sf = (sf * Decimal(str(panel_coverage_pct))) / Decimal("100")
    else:
        effective_sf = sf
        panel_coverage_pct = None

    # Line item name: panel name/color if given, else generic
    name_parts = [p for p in [panel_name, panel_color] if p]
    if name_parts:
        item_name = " ".join(name_parts)
        if "panel" not in item_name.lower():
            item_name += " Panels"
    else:
        item_name = "Wall Panels"

    line_items = [{
        "section":     "Wall Panels",
        "name":        item_name,
        "description": "",
        "calc_type":   "sf",
        "quantity":    float(effective_sf),
        "unit":        "SF",
        "unit_price":  float(combined_rate),
        "total_price": float(combined_rate * effective_sf),
    }]

    # Fixed add-ons (with quantity support) — always separate lines
    addons_fixed_cfg = cfg.get("addons_fixed", {})
    for entry in addons_fixed:
        if isinstance(entry, str):
            key, qty = entry, 1
        else:
            key = entry.get("key")
            qty = int(entry.get("qty", 1))
        addon = addons_fixed_cfg.get(key)
        if not addon or qty <= 0:
            continue
        price = Decimal(str(addon["price"]))
        label = addon.get("label", key)
        line_items.append({
            "section":     "Wall Panels",
            "name":        f"{label}" + (f" \u00d7 {qty}" if qty > 1 else ""),
            "description": "",
            "calc_type":   "fixed",
            "quantity":    qty,
            "unit":        "ea",
            "unit_price":  float(price),
            "total_price": float(price * qty),
        })

    total = sum(Decimal(str(i["total_price"])) for i in line_items)
    return {"type": "wall", "total": float(total), "line_items": line_items}


def calc_cabinet(
    linear_footage: float,
    budget: bool = False,
    cabinet_type: Optional[str] = None,
    addons_lf: List[str] = None,
    glass_doors: List[dict] = None,
    config: Optional[dict] = None,
) -> dict:
    cfg = (config or DEFAULT_PRICING_CONFIG)["cabinet"]

    lf = Decimal(str(linear_footage)) if linear_footage else Decimal("0")
    addons_lf   = addons_lf or []
    glass_doors = glass_doors or []

    # Resolve base rate: cabinet_type > budget flag > default
    types_cfg = cfg.get("types", {})
    if cabinet_type and cabinet_type in types_cfg:
        base_rate = Decimal(str(types_cfg[cabinet_type]["base_rate"]))
        type_label = types_cfg[cabinet_type]["label"]
    elif budget:
        base_rate = Decimal(str(cfg.get("base_rate_budget", 900)))
        type_label = "Cabinetry (budget)"
    else:
        base_rate = Decimal(str(cfg.get("base_rate", 1000)))
        type_label = "Cabinetry"

    addons_lf_cfg = cfg.get("addons_lf", {})

    # Split addons into:
    # - describable (e.g. LED) → separate visible line items
    # - non-describable (e.g. wood veneer, plywood) → folded into base rate silently
    describable_keys = [k for k in addons_lf if k in addons_lf_cfg and addons_lf_cfg[k].get("describable")]
    folded_keys      = [k for k in addons_lf if k in addons_lf_cfg and not addons_lf_cfg[k].get("describable")]

    # Fold non-describable addon rates into base rate
    folded_rate = base_rate + sum(
        Decimal(str(addons_lf_cfg[k]["price"])) for k in folded_keys
    )

    # Build description: LF × effective rate. No mention of folded addons.
    desc = f"{float(lf):.1f} LF \u00d7 ${float(folded_rate):,.0f}/LF"

    line_items = [{
        "section":     "Cabinetry",
        "name":        type_label,
        "description": "",
        "calc_type":   "lf",
        "quantity":    float(lf),
        "unit":        "LF",
        "unit_price":  float(folded_rate),
        "total_price": float(folded_rate * lf),
    }]

    # Describable addons (e.g. LED) → separate line items visible to client
    friendly_names = {
        "led_lighting":         "LED interior lighting",
        "wood_veneer":          "Wood veneer finish",
        "slim_shaker":          "Slim shaker doors",
        "plywood_construction": "Plywood box construction",
        "integrated_handles":   "Integrated / handleless doors",
        "luxury_finish":        "Luxury lacquer finish",
        "complex_design":       "Complex custom design",
        "difficult_install":    "Difficult installation",
    }
    for key in describable_keys:
        addon = addons_lf_cfg[key]
        rate  = Decimal(str(addon["price"]))
        line_items.append({
            "section":     "Cabinetry",
            "name":        friendly_names.get(key, addon.get("label", key)),
            "description": "",
            "calc_type":   "lf",
            "quantity":    float(lf),
            "unit":        "LF",
            "unit_price":  float(rate),
            "total_price": float(rate * lf),
        })

    # Glass doors → always separate line items (client needs to see them)
    glass_cfg = cfg.get("glass_doors", {})
    for gd in glass_doors:
        gtype = gd.get("type", "standard")
        qty   = int(gd.get("qty", 1))
        addon = glass_cfg.get(gtype) or glass_cfg.get("standard", {"price": 650})
        price = Decimal(str(addon["price"]))
        size_label = "large" if gtype == "large" else "standard"
        line_items.append({
            "section":     "Cabinetry",
            "name":        f"Glass door - {size_label}",
            "description": "",
            "calc_type":   "fixed",
            "quantity":    qty,
            "unit":        "ea",
            "unit_price":  float(price),
            "total_price": float(price * qty),
        })

    total = sum(Decimal(str(i["total_price"])) for i in line_items)
    return {"type": "cabinet", "total": float(total), "line_items": line_items}


def calc_mirror(square_footage: float, config: Optional[dict] = None) -> dict:
    cfg = (config or DEFAULT_PRICING_CONFIG)["mirror"]

    sf           = Decimal(str(square_footage)) if square_footage else Decimal("0")
    rate         = Decimal(str(cfg["rate"]))
    install_fee  = Decimal(str(cfg["minimum"]))  # fixed fee always added
    total_price  = sf * rate + install_fee

    line_items = [{
        "section":     "Mirrors",
        "name":        "Mirror",
        "description": "",
        "calc_type":   "sf",
        "quantity":    float(sf),
        "unit":        "SF",
        "unit_price":  float(rate),
        "total_price": float(total_price),
    }]

    return {"type": "mirror", "total": float(total_price), "line_items": line_items}


# ─── AUTO-CALCULATE FROM AI ZONES ─────────────────────────────

def calc_zone(zone: dict, config: Optional[dict] = None) -> dict:
    """Takes a zone dict from AI extraction, returns line_items."""
    ztype = zone.get("zone_type", "wall")

    if ztype == "wall":
        sf = zone.get("square_footage")
        w  = zone.get("wall_width_ft")
        h  = zone.get("wall_height_ft")
        if not sf and w and h:
            sf = w * h
        return calc_wall(
            square_footage     = sf or 0,
            addons_sf          = zone.get("addons_sf", []),
            addons_fixed       = zone.get("addons_fixed", []),
            panel_name         = zone.get("panel_name"),
            panel_color        = zone.get("panel_color"),
            panel_coverage_pct = zone.get("panel_coverage_pct"),
            config             = config,
        )

    elif ztype == "cabinet":
        return calc_cabinet(
            linear_footage = zone.get("linear_footage") or 0,
            budget         = zone.get("budget", False),
            cabinet_type   = zone.get("cabinet_type"),
            addons_lf      = zone.get("addons_lf", []),
            glass_doors    = zone.get("glass_doors", []),
            config         = config,
        )

    elif ztype == "mirror":
        return calc_mirror(zone.get("square_footage") or 0, config=config)

    return {"type": ztype, "total": 0, "line_items": []}


# ─── UI SCHEMA for frontend checkboxes ────────────────────────

def get_pricing_schema(config: Optional[dict] = None) -> dict:
    """Returns the pricing config reshaped as flat lists for frontend dropdowns/checkboxes."""
    cfg = config or DEFAULT_PRICING_CONFIG
    wall = cfg["wall"]
    cabinet = cfg["cabinet"]
    mirror = cfg["mirror"]

    tier_labels = {"large": "Large wall (250+ SF)", "medium": "Medium wall (100\u2013249 SF)", "small": "Small wall (<100 SF)"}

    return {
        "wall": {
            "base_rates": [
                {"key": k, "label": tier_labels.get(k, k), "rate": v}
                for k, v in wall["base_rates"].items()
            ],
            "addons_sf": [
                {"key": k, "label": v["label"], "price": v["price"]}
                for k, v in wall.get("addons_sf", {}).items()
            ],
            "addons_fixed": [
                {"key": k, "label": v["label"], "price": v["price"]}
                for k, v in wall.get("addons_fixed", {}).items()
            ],
        },
        "cabinet": {
            "base_rates": [
                {"key": "standard", "label": "Standard", "rate": cabinet["base_rate"]},
                {"key": "budget", "label": "Budget version", "rate": cabinet["base_rate_budget"]},
            ],
            "types": [
                {"key": k, "label": v["label"], "rate": v["base_rate"]}
                for k, v in cabinet.get("types", {}).items()
            ],
            "addons_lf": [
                {"key": k, "label": v["label"], "price": v["price"], "describable": v.get("describable", False)}
                for k, v in cabinet.get("addons_lf", {}).items()
            ],
            "glass_doors": [
                {"key": k, "label": v["label"], "price": v["price"]}
                for k, v in cabinet.get("glass_doors", {}).items()
            ],
        },
        "mirror": {
            "rate": mirror["rate"],
            "minimum": mirror["minimum"],
        },
        # Pass materials, colors, and services through directly
        "materials": cfg.get("materials", {}),
        "colors": cfg.get("colors", []),
        "services": cfg.get("services", {}),
    }