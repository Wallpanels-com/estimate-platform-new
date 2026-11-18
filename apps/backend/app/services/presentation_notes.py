"""Shared client-facing zone notes, independent of priced scope."""
from copy import deepcopy
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from .page_access import allowed_pages
from .proposal_display import _View

# Preserve notes saved during the owner trial; no migration or reset.
KEY = 'zone_presentation_notes_trial'
Note = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=1000)]


class NotesInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    notes: list[Note] = Field(max_length=20)

    @field_validator('notes')
    @classmethod
    def printable(cls, values):
        if any(any(ord(c) < 32 and c not in '\n\t' for c in text) for text in values):
            raise ValueError('Notes must contain readable text.')
        return values


def available(user):
    if not getattr(user, "is_active", False):
        return False
    identity = getattr(user, "_portal_profile", None)
    return "estimates" in allowed_pages(user) and (
        identity is None or identity.get("module") in (None, "estimating")
    )


def entries(estimate):
    return (getattr(estimate, 'pdf_layout', None) or {}).get(KEY, {})


def notes_for(estimate, zone):
    return list(entries(estimate).get(str(zone.id), {}).get('notes', []))


def select_notes(estimate, zone, data):
    layout = dict(getattr(estimate, 'pdf_layout', None) or {})
    layout[KEY] = dict(entries(estimate))
    layout[KEY][str(zone.id)] = {'notes': list(data.notes), 'override': True}
    estimate.pdf_layout = layout


def remap(estimate, zone_map, *, inherited=False):
    return {zone_map[key]: deepcopy(value) | ({'override': False} if inherited else {})
            for key, value in entries(estimate).items() if key in zone_map}


def sync_notes(pre, final, zone_map):
    """Follow Pre unless the Final note list was explicitly edited (even to empty)."""
    inherited = remap(pre, zone_map, inherited=True)
    original = entries(final)
    values = deepcopy(original)
    valid = {str(z.id) for z in final.zones}
    for target in zone_map.values():
        if target not in valid or original.get(target, {}).get('override'):
            continue
        if target in inherited:
            values[target] = inherited[target]
        else:
            values.pop(target, None)
    values = {key: value for key, value in values.items() if key in valid}
    if values != original:
        final.pdf_layout = dict(final.pdf_layout or {}) | {KEY: values}
        return True
    return False


def presentation_view(estimate, user):
    if not available(user) or getattr(estimate, 'type', None) not in ('pre', 'final'):
        return estimate
    view = _View(estimate)
    view._presentation_notes_enabled = True
    view.zones = []
    for source in estimate.zones:
        zone = _View(source)
        zone._presentation_notes = notes_for(estimate, source)
        view.zones.append(zone)
    return view
