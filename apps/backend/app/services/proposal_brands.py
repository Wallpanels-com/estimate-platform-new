"""Explicit proposal artwork profiles; never changes pricing or customer content."""
from dataclasses import dataclass
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / 'assets/proposals'
DEFAULT_BRAND = 'wallpanels'


@dataclass(frozen=True)
class ProposalBrand:
    key: str
    label: str
    assets: Path
    company_pages: int
    logo_ratio: float


BRANDS = {
    'wallpanels': ProposalBrand('wallpanels', 'Wallpanels', ASSETS, 25, 3),
    'verona': ProposalBrand('verona', 'Verona Home', ASSETS / 'verona', 29, 3),
}


def brand_key(estimate):
    layout = getattr(estimate, 'pdf_layout', None) or {}
    selected = layout.get('proposal_brand') if isinstance(layout, dict) else None
    return selected if isinstance(selected, str) and selected in BRANDS else DEFAULT_BRAND


def profile(brand=DEFAULT_BRAND):
    # No user-provided paths: only these two approved profiles may be exported.
    if brand not in BRANDS:
        raise ValueError('Choose WallPanels or Verona Home for the presentation.')
    return BRANDS[brand]


def select_brand(estimate, brand):
    profile(brand)
    layout = dict(getattr(estimate, 'pdf_layout', None) or {})
    layout['proposal_brand'] = brand
    estimate.pdf_layout = layout


def initial_layout(estimate):
    # A newly created Final inherits the chosen brand, never old zone/photo IDs.
    from .proposal_display import display_options
    result = {'proposal_brand': brand_key(estimate)} if brand_key(estimate) != DEFAULT_BRAND else {}
    options = display_options(estimate)
    if not options.show_grand_total or not options.show_calculations:
        result['presentation_options'] = vars(options)
    return result or None
