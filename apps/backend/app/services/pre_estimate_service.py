"""Local version switch. V1 is frozen; V2 changes presentation only."""

# Retain the existing layout-test imports for the frozen V1 contract.
from .pre_estimate_v1 import _fonts, _gallery, _item_detail, _zone_pages


def design_version():
    from app.core.config import settings

    return settings.PRE_ESTIMATE_DESIGN


def generate_pre_estimate(est, output_path):
    if design_version() == "v1":
        from .pre_estimate_v1 import generate_pre_estimate as render
    else:
        from .pre_estimate_v2 import generate_pre_estimate as render
    return render(est, output_path)
