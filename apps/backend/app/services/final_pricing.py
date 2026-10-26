"""Read-only presentation totals and pre-export checks, using saved line amounts.

No rate lookup, rule-engine call or price write occurs here. Percentage display
adjustments are applied once; cent residuals are distributed deterministically
so visible component, zone and project totals reconcile exactly.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

CENT = Decimal("0.01")


def numeric(value):
    return Decimal(str(value if value is not None else 0))


def key(obj):
    return str(getattr(obj, "id", None) or id(obj))


def cents(value):
    return numeric(value).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class Quote:
    factor: Decimal
    item_prices: dict
    zone_prices: dict
    gross: Decimal
    discount: Decimal
    component_total: Decimal
    grand_total: Decimal
    manual_adjustment: Decimal
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def quote(estimate, zones=None):
    zones = list(zones if zones is not None else estimate.zones)
    entries = []
    seen = set()
    errors = []
    warnings = []
    for z in zones:
        for item in z.line_items:
            ident = key(item)
            if ident in seen:
                errors.append(
                    "A component occurs in more than one zone. Review the estimate before exporting."
                )
                continue
            seen.add(ident)
            entries.append((z, item))
    # Direct scope has no physical zone, but remains part of every project total.
    for item in getattr(estimate, "line_items", []) or []:
        if getattr(item, "zone_id", None) is None and key(item) not in seen:
            entries.append((None, item))
            seen.add(key(item))
    markup = numeric(getattr(estimate, "markup_pct", 0))
    discount_pct = numeric(getattr(estimate, "discount_pct", 0))
    if not markup.is_finite() or not discount_pct.is_finite():
        errors.append(
            "Markup or discount is invalid. Review the estimate before exporting."
        )
        markup = discount_pct = Decimal(0)
    factor = (1 + markup / 100) * (1 - discount_pct / 100)
    amounts = []
    for _, item in entries:
        if not str(getattr(item, "name", "") or "").strip():
            errors.append("A component has no name. Add its name before exporting.")
        value = numeric(item.total_price)
        if not value.is_finite():
            errors.append(
                "A component amount is invalid. Review the estimate before exporting."
            )
            value = Decimal(0)
        amounts.append(value)
        if getattr(item, "is_tbd", False):
            warnings.append(
                "Some items need pricing confirmation. Unpriced scope is excluded from the total."
            )
            if value:
                errors.append(
                    "An unpriced item has a saved amount. Confirm its pricing before exporting."
                )
        elif value == 0:
            warnings.append(
                "This estimate contains zero-value items. Review these amounts before exporting."
            )
        calc = str(getattr(item, "calc_type", "manual")).lower()
        qty = getattr(item, "quantity", None)
        rate = getattr(item, "unit_price", None)
        if (
            calc in ("sf", "lf", "qty")
            and not getattr(item, "is_tbd", False)
            and (qty is None or rate is None)
        ):
            warnings.append(
                "Some calculated items have incomplete measurements or unit prices. Saved amounts will be used."
            )
        if (
            qty is not None
            and rate is not None
            and cents(numeric(qty) * numeric(rate)) != cents(value)
        ):
            warnings.append(
                "Some component totals differ from quantity × unit price. Saved manual amounts will be used."
            )
    raw_total = sum(amounts, Decimal(0))
    if hasattr(estimate, "subtotal") and cents(estimate.subtotal) != cents(raw_total):
        errors.append(
            "The saved subtotal does not match the component totals. Review the estimate before exporting."
        )
    manual = bool(getattr(estimate, "manual_override", False))
    if (
        hasattr(estimate, "final_total")
        and not manual
        and cents(estimate.final_total) != cents(raw_total)
    ):
        errors.append(
            "The saved project total does not match the component totals. Review the estimate before exporting."
        )
    if any(not z.line_items for z in zones) or not entries:
        warnings.append(
            "Some zones have no priced components. Review their scope before exporting."
        )
    exact = [v * factor for v in amounts]
    target = cents(raw_total * factor)
    units = [int((v / CENT).to_integral_value(rounding=ROUND_FLOOR)) for v in exact]
    delta = int(target / CENT) - sum(units)
    order = sorted(range(len(exact)), key=lambda n: (-(exact[n] / CENT - units[n]), n))
    for n in order[:delta]:
        units[n] += 1
    prices = {
        key(item): Decimal(units[n]) * CENT for n, (_, item) in enumerate(entries)
    }
    zone_prices = {
        key(z): sum((prices[key(i)] for i in z.line_items), Decimal(0)) for z in zones
    }
    grand = cents(numeric(estimate.final_total) * factor) if manual else target
    adjustment = grand - target
    if adjustment:
        warnings.append(
            "A manual project total is active. Its adjustment is shown separately in the investment summary."
        )
    gross = cents(raw_total * (1 + markup / 100))
    return Quote(
        factor,
        prices,
        zone_prices,
        gross,
        gross - target,
        target,
        grand,
        adjustment,
        list(dict.fromkeys(warnings)),
        list(dict.fromkeys(errors)),
    )
