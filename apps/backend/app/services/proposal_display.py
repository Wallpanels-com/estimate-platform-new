"""Presentation-only visibility; saved scope, quantities and prices stay intact."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DisplayOptions:
    show_grand_total: bool = True
    show_calculations: bool = True


def display_options(estimate):
    layout = getattr(estimate, 'pdf_layout', None)
    values = layout.get('presentation_options') if isinstance(layout, dict) else None
    values = values if isinstance(values, dict) else {}
    return DisplayOptions(**{key: values.get(key) is not False for key in DisplayOptions.__dataclass_fields__})


def select_display_options(estimate, changes):
    layout = dict(getattr(estimate, 'pdf_layout', None) or {})
    values = vars(display_options(estimate)) | changes
    layout['presentation_options'] = values
    estimate.pdf_layout = layout


# Strip arithmetic only when a measurement unit or currency identifies pricing.
# Product dimensions such as "2 x 4 lumber" and material codes remain verbatim.
_NUMBER = r'\d[\d,]*(?:\.\d+)?'
_UNIT = r'(?:square\s*(?:feet|foot)|sq\.?\s*ft\.?|linear(?:\s*(?:feet|foot))?|lin\.?\s*ft\.?|SF|LF|SQFT|ft²|feet|foot|ft|ea|pcs?|units?)'
_RATE = rf'\$?\s*{_NUMBER}(?:\s*/\s*{_UNIT})?'
_FORMULA = re.compile(
    rf'(?<![\w.])(?:{_NUMBER}\s*{_UNIT}|{_UNIT}\s*{_NUMBER})\s*[×x*]\s*{_RATE}(?![\w.])'
    rf'|(?<![\w.]){_NUMBER}\s*[×x*]\s*\$\s*{_NUMBER}(?![\w.])', re.I)
_UNIT_PRICE = re.compile(rf'(?<!\w){_NUMBER}\s*{_UNIT}\s*\|\s*Unit price:\s*{_RATE}', re.I)


def without_calculations(value):
    value = str(value or '')
    # A dimension ending in another unit is not a quantity × rate expression.
    def remove(match):
        tail = value[match.end():]
        return match.group() if re.match(rf'\s*{_UNIT}\b', tail, re.I) else ''
    cleaned = _FORMULA.sub(remove, value)
    cleaned = _UNIT_PRICE.sub('', cleaned)
    cleaned = re.sub(r'\(\s*\)', '', cleaned)
    cleaned = re.sub(r'\s*[-–—|·]\s*(?=[-–—|·]|$)', '', cleaned)
    cleaned = re.sub(r'^[\s\-–—|·]+|[\s\-–—|·]+$', '', cleaned)
    return re.sub(r'[ \t]{2,}', ' ', cleaned).strip()


class _View:
    def __init__(self, source):
        self._source = source

    def __getattr__(self, name):
        return getattr(self._source, name)


class _Item(_View):
    _hide_calculations = True

    @property
    def name(self):
        return without_calculations(self._source.name) or 'Scope item'

    @property
    def description(self):
        return without_calculations(getattr(self._source, 'description', None))


def presentation_view(estimate):
    if display_options(estimate).show_calculations:
        return estimate
    # Reuse item proxies across zone/direct collections, including fixtures with
    # no database IDs. Pricing still sees the exact original numeric fields.
    items = {}
    def item(source):
        return items.setdefault(id(source), _Item(source))
    view = _View(estimate)
    view.zones = []
    for source in getattr(estimate, 'zones', []) or []:
        zone = _View(source)
        zone.line_items = [item(i) for i in source.line_items]
        view.zones.append(zone)
    view.line_items = [item(i) for i in getattr(estimate, 'line_items', []) or []]
    return view
