"""Shared ordered presentation photos; owner-private QA remains isolated."""
from fastapi import HTTPException
from pydantic import BaseModel, Field, ConfigDict
from typing import Annotated
from .page_access import can_view_sales, allowed_pages
from .proposal_display import _View
from .final_zone_photos import selected_slot

# Keep the stored key and capability name for existing trial selections/clients.
KEY = 'final_zone_photo_pairs_trial'
PRIVATE_KEY = 'private_preview_owner'


def available(user):
    if not getattr(user, "is_active", False):
        return False
    identity = getattr(user, "_portal_profile", None)
    return "estimates" in allowed_pages(user) and (
        identity is None or identity.get("module") in (None, "estimating")
    )


def private_available(user):
    return can_view_sales(user)


def can_read(layout, user):
    owner = (layout or {}).get(PRIVATE_KEY)
    return not owner or (str(getattr(user, 'id', '')) == owner and private_available(user))


def require_read(layout, user):
    if not can_read(layout, user):
        raise HTTPException(404, 'Estimate not found')


class PhotoPairInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slots: list[Annotated[int, Field(strict=True, ge=1, le=4)]] = Field(min_length=1, max_length=2)


def slots_for(estimate, zone):
    saved = (getattr(estimate, 'pdf_layout', None) or {}).get(KEY, {}).get(str(zone.id), [])
    valid = {i.slot for i in zone.images}
    slots = list(dict.fromkeys(s for s in saved if s in valid))[:2]
    default = selected_slot(estimate, zone)
    return slots or ([default] if default is not None else [])


def select_pair(estimate, zone, slots):
    if len(set(slots)) != len(slots) or not set(slots).issubset({i.slot for i in zone.images}):
        raise ValueError('Choose one or two different existing photos from this zone.')
    layout = dict(estimate.pdf_layout or {})
    layout[KEY] = dict(layout.get(KEY, {})) | {str(zone.id): slots}
    estimate.pdf_layout = layout


def presentation_view(estimate, user):
    if not available(user) or getattr(estimate, 'type', None) != 'final':
        return estimate
    view = _View(estimate)
    view.zones = []
    for source in estimate.zones:
        zone = _View(source)
        zone._presentation_slots = slots_for(estimate, source)
        view.zones.append(zone)
    return view
