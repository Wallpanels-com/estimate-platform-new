"""Local version switch. V1 is frozen; V2 changes presentation only."""

# Retain the existing layout-test imports for the frozen V1 contract.
from .pre_estimate_v1 import _fonts, _gallery, _item_detail, _zone_pages
from pathlib import Path
import tempfile
from .final_estimate_service import load_company_slides, compose_final_pdf


class _PreEstimateView:
    """Final-only markup must not leak into the frozen Pre renderers."""
    markup_pct = 0

    def __init__(self, estimate):
        self._estimate = estimate

    def __getattr__(self, name):
        return getattr(self._estimate, name)


def design_version():
    from app.core.config import settings

    return settings.PRE_ESTIMATE_DESIGN


def generate_pre_estimate(est, output_path):
    company = load_company_slides()  # Fail closed before rendering any partial proposal.
    if design_version() == "v1":
        from .pre_estimate_v1 import generate_pre_estimate as render
    else:
        from .pre_estimate_v2 import generate_pre_estimate as render
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pre-client-', dir=output_path.parent) as folder:
        client = render(_PreEstimateView(est), Path(folder) / 'client.pdf')
        return compose_final_pdf(client, output_path, company)
