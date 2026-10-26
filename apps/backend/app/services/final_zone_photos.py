"""Final-only, per-zone photo selection; existing uploads stay untouched."""

PHOTO_REQUIRED = (
    "Add at least one photo to every zone before generating a Final Estimate."
)


def selected_slot(estimate, zone):
    images = sorted(getattr(zone, "images", []) or [], key=lambda image: image.slot)
    layout = getattr(estimate, "pdf_layout", None) or {}
    choices = layout.get("final_zone_photos", {})
    choice = (
        choices.get(str(getattr(zone, "id", ""))) if isinstance(choices, dict) else None
    )
    return next(
        (image.slot for image in images if image.slot == choice),
        images[0].slot if images else None,
    )


def select_photo(estimate, zone, slot):
    if not any(image.slot == slot for image in zone.images):
        raise ValueError("Choose an existing photo from this zone.")
    layout = dict(getattr(estimate, "pdf_layout", None) or {})
    choices = dict(layout.get("final_zone_photos", {}))
    choices[str(zone.id)] = slot
    layout["final_zone_photos"] = choices
    estimate.pdf_layout = layout
