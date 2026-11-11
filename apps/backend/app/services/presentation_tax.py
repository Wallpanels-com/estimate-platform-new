"""Optional proposal tax. No saved prices, quotes, XLSX or pricing rules change."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

CENT = Decimal('0.01')


class TaxOptions(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    enabled: StrictBool = False
    mode: Literal['percent', 'amount'] = 'percent'
    rate: Decimal = Field(default=Decimal(7), ge=0, le=100, decimal_places=4)
    amount: Decimal = Field(default=Decimal(0), ge=0, le=Decimal('999999999999.99'), decimal_places=2)


def tax_options(estimate):
    layout = getattr(estimate, 'pdf_layout', None)
    value = layout.get('presentation_tax') if isinstance(layout, dict) else None
    try:
        return TaxOptions.model_validate(value or {})
    except ValidationError as error:
        raise ValueError('Tax settings are invalid. Review the presentation tax settings.') from error


def select_tax(estimate, options):
    layout = dict(getattr(estimate, 'pdf_layout', None) or {})
    layout['presentation_tax'] = options.model_dump(mode='json')
    estimate.pdf_layout = layout


@dataclass(frozen=True)
class TaxBreakdown:
    subtotal: Decimal
    tax: Decimal
    grand_total: Decimal
    label: str


def breakdown(estimate, subtotal):
    options = tax_options(estimate)
    # Match the existing renderer's displayed subtotal before adding the
    # separate tax line; tax itself always uses decimal, half-up cent rounding.
    subtotal = Decimal(format(Decimal(str(subtotal)), '.2f'))
    if options.enabled and (not subtotal.is_finite() or subtotal < 0):
        raise ValueError('Tax requires a valid, non-negative project subtotal.')
    tax = (subtotal * options.rate / 100 if options.mode == 'percent' else options.amount) if options.enabled else Decimal(0)
    tax = tax.quantize(CENT, rounding=ROUND_HALF_UP)
    rate = format(options.rate, 'f').rstrip('0').rstrip('.') if '.' in format(options.rate, 'f') else str(options.rate)
    label = f'Tax ({rate}%)' if options.mode == 'percent' else 'Tax'
    return TaxBreakdown(subtotal, tax, subtotal + tax, label)


def proposal_subtotal(estimate):
    if getattr(estimate, 'type', 'pre') == 'final':
        from .final_pricing import quote
        pricing = quote(estimate)
        if pricing.errors:
            raise ValueError(' '.join(pricing.errors))
        return pricing.grand_total
    # Pre uses its established discount-only basis, including unassigned scope.
    total = sum((Decimal(str(i.total_price or 0)) for i in estimate.line_items), Decimal(0))
    return total * (1 - Decimal(str(getattr(estimate, 'discount_pct', 0) or 0)) / 100)


def draw_totals(c, estimate, subtotal, x, y, width, height=88, subtitle='', unpriced=False):
    """Three measured columns inside the existing reserved total band."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.lib.colors import HexColor
    values = breakdown(estimate, subtotal)
    c.saveState()
    c.setFillColor(HexColor('#ECEDEB'))
    c.rect(x, y, width, height, fill=1, stroke=0)
    gap, inset = 24, 24
    cell = (width - 2 * inset - 2 * gap) / 3
    entries = [('Subtotal', values.subtotal), (values.label, values.tax), ('Grand Total', values.grand_total)]
    for n, (label, value) in enumerate(entries):
        left = x + inset + n * (cell + gap)
        c.setFillColor(HexColor('#292724'))
        c.setFont('WP-Medium', 11)
        c.drawString(left, y + height - 18, label.upper())
        if n == 0 and subtitle:
            c.setFillColor(HexColor('#746D65'))
            c.setFont('WP-Regular', 10)
            # The annotation is bounded too, including very large adjustments.
            if pdfmetrics.stringWidth(subtitle, 'WP-Regular', 10) <= cell:
                c.drawString(left, y + height - 33, subtitle)
        value = 'To be confirmed' if unpriced else f'${value:,.2f}'
        size = 32 if n == 2 else 26
        while pdfmetrics.stringWidth(value, 'WP-Bold' if n == 2 else 'WP-Medium', size) > cell and size > 12:
            size -= 1
        c.setFillColor(HexColor('#292724'))
        c.setFont('WP-Bold' if n == 2 else 'WP-Medium', size)
        c.drawString(left, y + 18, value)
    c.restoreState()
