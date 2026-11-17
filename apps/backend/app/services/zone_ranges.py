"""Shared Pre-estimate zone ranges. Original item prices are never changed."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Annotated
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from .page_access import allowed_pages
from .proposal_display import _View
from .presentation_tax import breakdown

# Preserve the saved pilot settings; no data migration or reset on rollout.
KEY = 'pre_zone_ranges_trial'
CENT = Decimal('0.01')
LIMIT = Decimal('999999999999.99')
Price = Annotated[Decimal, Field(ge=0, le=LIMIT, decimal_places=2)]


def available(user):
    if not getattr(user, "is_active", False):
        return False
    identity = getattr(user, "_portal_profile", None)
    return "estimates" in allowed_pages(user) and (
        identity is None or identity.get("module") in (None, "estimating")
    )


class RangeOptions(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    enabled: StrictBool
    mode: Literal['auto', 'manual'] = 'auto'
    lower: Price | None = None
    upper: Price | None = None

    @model_validator(mode='after')
    def bounds(self):
        if self.enabled and self.mode == 'manual':
            if self.lower is None or self.upper is None or self.lower > self.upper:
                raise ValueError('Enter a valid lower and upper price. The upper price must not be lower.')
        return self


def cents(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def base_price(estimate, zone):
    factor = 1 - Decimal(str(getattr(estimate, 'discount_pct', 0) or 0)) / 100
    return cents(sum((Decimal(str(i.total_price or 0)) for i in zone.line_items), Decimal(0)) * factor)


def settings(estimate):
    return (getattr(estimate, 'pdf_layout', None) or {}).get(KEY, {})


def zone_values(estimate, zone):
    base = base_price(estimate, zone)
    saved = settings(estimate).get(str(zone.id), {})
    options = RangeOptions.model_validate({'enabled': False} | {k: v for k, v in saved.items() if k != 'basis'})
    auto = (cents(base * Decimal('.90')), cents(base * Decimal('1.15')))
    lower, upper = ((options.lower, options.upper) if options.mode == 'manual' else auto) if options.enabled else (base, base)
    return {'options': options.model_dump(mode='json'), 'basis': str(base),
            'automatic_lower': str(auto[0]), 'automatic_upper': str(auto[1]),
            'lower': str(lower), 'upper': str(upper),
            'stale': bool(options.enabled and options.mode == 'manual' and saved.get('basis') != str(base))}


def select_range(estimate, zone, options):
    base = base_price(estimate, zone)
    if options.enabled and base <= 0:
        raise ValueError('Add confirmed positive pricing before enabling a zone range.')
    layout = dict(getattr(estimate, 'pdf_layout', None) or {})
    # Drop obsolete zone IDs without changing surviving selections.
    valid = {str(z.id) for z in estimate.zones}
    values = {key: value for key, value in settings(estimate).items() if key in valid}
    values[str(zone.id)] = options.model_dump(mode='json') | {'basis': str(base)}
    layout[KEY] = values
    estimate.pdf_layout = layout


def snapshot(estimate):
    zones = {str(z.id): zone_values(estimate, z) for z in estimate.zones}
    active = any(v['options']['enabled'] for v in zones.values())
    direct = [i for i in estimate.line_items if getattr(i, 'zone_id', None) is None]
    factor = 1 - Decimal(str(getattr(estimate, 'discount_pct', 0) or 0)) / 100
    direct_total = cents(sum((Decimal(str(i.total_price or 0)) for i in direct), Decimal(0)) * factor)
    lower = sum((Decimal(v['lower']) for v in zones.values()), direct_total)
    upper = sum((Decimal(v['upper']) for v in zones.values()), direct_total)
    if not active:
        # Untouched estimates retain the established project-wide range.
        total = sum((Decimal(str(i.total_price or 0)) for i in estimate.line_items), Decimal(0)) * factor
        lower, upper = cents(total * Decimal('.90')), cents(total * Decimal('1.15'))
    low_tax, high_tax = breakdown(estimate, lower), breakdown(estimate, upper)
    return {'active': active, 'zones': zones, 'direct_total': str(direct_total), 'lower': str(lower), 'upper': str(upper),
            'tax_lower': str(low_tax.tax), 'tax_upper': str(high_tax.tax),
            'grand_lower': str(low_tax.grand_total), 'grand_upper': str(high_tax.grand_total),
            'tax_label': low_tax.label}


def presentation_view(estimate, user):
    # All authorized employees render the same saved bounds; never alter ORM data or Final.
    if not available(user) or getattr(estimate, 'type', None) != 'pre' or not settings(estimate):
        return estimate
    values = snapshot(estimate)
    if not values['active']:
        return estimate
    view = _View(estimate)
    view._pre_range_summary = values
    view.zones = []
    for source in estimate.zones:
        zone = _View(source)
        value = values['zones'][str(source.id)]
        zone._pre_range = value if value['options']['enabled'] else None
        zone._pre_exact = value['basis']
        view.zones.append(zone)
    return view


def price_label(zone):
    value = getattr(zone, '_pre_range', None)
    if value:
        return f"${Decimal(value['lower']):,.2f} – ${Decimal(value['upper']):,.2f}"
    return None
