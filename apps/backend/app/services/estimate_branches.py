"""Independent Final branch with field-level inheritance from Pre.

Stable entity mappings and explicit override/tombstone records preserve edits,
including edits reverted to their old value. Synchronization is transactional
and runs when Final is opened/exported. Files are copied so removal in either
branch cannot invalidate the other. No pricing rules are introduced here.
"""

from copy import deepcopy
from pathlib import Path
import shutil
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session, selectinload
from app.models.estimate import Estimate, EstimateZone, LineItem, EstimateImage
from app.core.config import settings

FIELDS = {
    "estimate": (
        "title",
        "room_name",
        "wall_name",
        "client_name",
        "project_name",
        "prepared_by",
        "estimate_date",
        "description",
        "notes",
        "wall_width_ft",
        "wall_height_ft",
        "square_footage",
        "markup_pct",
        "discount_pct",
        "manual_override",
        "final_total",
    ),
    "zones": (
        "sort_order",
        "zone_type",
        "label",
        "room_name",
        "wall_name",
        "wall_width_ft",
        "wall_height_ft",
        "square_footage",
        "linear_footage",
        "notes",
    ),
    "items": (
        "section",
        "sort_order",
        "name",
        "description",
        "calc_type",
        "quantity",
        "unit",
        "unit_price",
        "original_unit_price",
        "total_price",
        "is_tbd",
    ),
    "images": ("slot", "file_path", "original_name"),
}
MODELS = {"zones": EstimateZone, "items": LineItem, "images": EstimateImage}


def values(obj, kind):
    return {field: deepcopy(getattr(obj, field)) for field in FIELDS[kind]}


def state_empty():
    return {
        "version": 1,
        "maps": {k: {} for k in MODELS},
        "overrides": {},
        "deleted": {k: [] for k in MODELS},
    }


def image_copy(path, estimate_id, zone_id=None):
    source = Path(path)
    if not source.is_file():
        return path  # retain the missing reference; the renderer reports it
    target = (
        Path(settings.STORAGE_PATH)
        / "images"
        / str(estimate_id)
        / str(zone_id or "inherited")
        / f"{uuid.uuid4()}{source.suffix}"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return str(target)


async def loaded(db, id, lock=False):
    query = (
        select(Estimate)
        .where(Estimate.id == id)
        .options(
            selectinload(Estimate.zones).selectinload(EstimateZone.line_items),
            selectinload(Estimate.zones).selectinload(EstimateZone.images),
            selectinload(Estimate.line_items),
            selectinload(Estimate.images),
        )
        .execution_options(populate_existing=True)
    )
    if lock:
        query = query.with_for_update()
    return (await db.execute(query)).scalar_one_or_none()


async def clone(db, src, mode):
    dst = Estimate(
        id=uuid.uuid4(),
        user_id=src.user_id,
        type=mode,
        status=src.status,
        subtotal=src.subtotal,
        created_by_name=src.created_by_name,
        updated_by_name=src.updated_by_name,
        **values(src, "estimate"),
    )
    db.add(dst)
    await db.flush()
    st = state_empty()
    for kind, entities in [
        ("zones", src.zones),
        ("items", src.line_items),
        ("images", src.images),
    ]:
        for obj in entities:
            data = values(obj, kind)
            ident = uuid.uuid4()
            if kind != "zones":
                data["zone_id"] = (
                    uuid.UUID(st["maps"]["zones"][str(obj.zone_id)])
                    if obj.zone_id
                    else None
                )
            if kind == "images":
                data["file_path"] = image_copy(
                    obj.file_path, dst.id, data.get("zone_id")
                )
            db.add(MODELS[kind](id=ident, estimate_id=dst.id, **data))
            st["maps"][kind][str(obj.id)] = str(ident)
        await db.flush()
    return dst, st


def photo_key(image, zone_map=None):
    zid = str(image.zone_id) if image.zone_id else "direct"
    if zone_map:
        zid = next((k for k, v in zone_map.items() if v == zid), zid)
    return f"photo:{zid}:{image.slot}"


@event.listens_for(Session, "before_flush")
def remember_final_edits(session, context, instances):
    if session.info.get("branch_sync"):
        return
    for obj in list(session.dirty) + list(session.deleted) + list(session.new):
        kind = (
            "estimate"
            if isinstance(obj, Estimate)
            else next((k for k, m in MODELS.items() if isinstance(obj, m)), None)
        )
        if not kind:
            continue
        est = obj if kind == "estimate" else session.get(Estimate, obj.estimate_id)
        if not est or not est.source_estimate_id:
            continue
        state = deepcopy(est.branch_state or state_empty())
        key = "estimate" if kind == "estimate" else str(obj.id)
        if obj in session.deleted and kind != "estimate":
            sources = [k for k, v in state["maps"][kind].items() if v == key]
            state["deleted"][kind] = list(set(state["deleted"][kind] + sources))
        fields = {
            f for f in FIELDS[kind] if inspect(obj).attrs[f].history.has_changes()
        }
        if kind == "estimate" and not obj.manual_override:
            fields.discard("final_total")
        if kind == "items":
            if inspect(obj).attrs.zone_id.history.has_changes():
                fields.add("zone_id")
            if fields & {"quantity", "unit_price"}:
                fields.discard("total_price")
        if kind == "images":
            state["overrides"][photo_key(obj, state["maps"]["zones"])] = ["photo"]
        if fields:
            state["overrides"][key] = sorted(
                set(state["overrides"].get(key, [])) | fields
            )
        est.branch_state = state


async def synchronize(db, final):
    if not final.source_estimate_id:
        return final
    pre = await loaded(db, final.source_estimate_id, lock=True)
    final = await loaded(db, final.id, lock=True)
    if not pre or pre.deleted_at:
        return final
    db.sync_session.info["branch_sync"] = True
    try:
        state = deepcopy(final.branch_state or state_empty())
        changed = False
        removed_zones = []
        for field, val in values(pre, "estimate").items():
            if field == "final_total":
                continue
            if (
                field not in state["overrides"].get("estimate", [])
                and getattr(final, field) != val
            ):
                setattr(final, field, val)
                changed = True
        zone_map = state["maps"]["zones"]
        for kind, entities, targets in [
            ("zones", pre.zones, final.zones),
            ("items", pre.line_items, final.line_items),
            ("images", pre.images, final.images),
        ]:
            mapping = state["maps"][kind]
            by_target = {str(o.id): o for o in targets}
            source_ids = {str(o.id) for o in entities}
            # Deleted source data disappears only when its Final counterpart is untouched.
            for source, target in list(mapping.items()):
                if source in source_ids:
                    continue
                obj = by_target.get(target)
                if kind == "zones":
                    if obj:
                        removed_zones.append(obj)
                    continue
                protected = bool(state["overrides"].get(target))
                if kind == "images" and obj:
                    protected |= photo_key(obj, zone_map) in state["overrides"]
                replaced = (
                    kind == "images"
                    and obj
                    and any(
                        i.slot == obj.slot
                        and zone_map.get(str(i.zone_id)) == str(obj.zone_id)
                        for i in entities
                    )
                )
                if obj and not protected and not replaced:
                    await db.delete(obj)
                    changed = True
            for obj in entities:
                sid = str(obj.id)
                if sid in state["deleted"][kind]:
                    continue
                target = by_target.get(mapping.get(sid, ""))
                data = values(obj, kind)
                if kind != "zones":
                    zid = zone_map.get(str(obj.zone_id)) if obj.zone_id else None
                    if obj.zone_id and (
                        str(obj.zone_id) in state["deleted"]["zones"] or not zid
                    ):
                        continue
                    data["zone_id"] = uuid.UUID(zid) if zid else None
                if kind == "images":
                    key = photo_key(obj)
                    if key in state["overrides"]:
                        continue
                if target is None:
                    if kind == "images":
                        # Replacement inherits the old slot unless Final has selected/replaced it.
                        target = next(
                            (
                                i
                                for i in targets
                                if i.zone_id == data["zone_id"]
                                and i.slot == obj.slot
                                and i not in db.deleted
                            ),
                            None,
                        )
                    if target is None:
                        target = MODELS[kind](
                            id=uuid.uuid4(),
                            estimate_id=final.id,
                            **{
                                **data,
                                **(
                                    {
                                        "file_path": image_copy(
                                            obj.file_path, final.id, data.get("zone_id")
                                        )
                                    }
                                    if kind == "images"
                                    else {}
                                ),
                            },
                        )
                        db.add(target)
                        mapping[sid] = str(target.id)
                        changed = True
                        continue
                    mapping[sid] = str(target.id)
                locked = state["overrides"].get(str(target.id), [])
                for field, val in data.items():
                    if field in locked or (
                        kind == "items" and field == "zone_id" and "zone_id" in locked
                    ):
                        continue
                    if kind == "images" and field == "file_path":
                        # Compare contents; independent copies have intentionally different paths.
                        import hashlib

                        a, b = Path(val), Path(target.file_path)
                        if (
                            a.is_file()
                            and b.is_file()
                            and hashlib.sha256(a.read_bytes()).digest()
                            == hashlib.sha256(b.read_bytes()).digest()
                        ):
                            continue
                        val = image_copy(val, final.id, target.zone_id)
                    if getattr(target, field) != val:
                        setattr(target, field, val)
                        changed = True
                if (
                    kind == "items"
                    and "total_price" not in locked
                    and set(locked) & {"quantity", "unit_price"}
                    and target.quantity is not None
                    and target.unit_price is not None
                ):
                    target.total_price = target.quantity * target.unit_price
                    changed = True
            await db.flush()
        # Merge/reparent children first. Deleting a removed source zone before
        # this step would cascade-delete an item that moved into another zone.
        for zone in removed_zones:
            await db.refresh(zone, ["line_items", "images"])
            protected = bool(state["overrides"].get(str(zone.id))) or any(
                state["overrides"].get(str(child.id))
                or (
                    isinstance(child, EstimateImage)
                    and photo_key(child, zone_map) in state["overrides"]
                )
                or str(child.id)
                not in (
                    set(state["maps"]["items"].values())
                    | set(state["maps"]["images"].values())
                )
                for child in [*zone.line_items, *zone.images]
            )
            if not protected:
                await db.delete(zone)
                changed = True
        await db.flush()
        final.branch_state = state
        await db.flush()
        final = await loaded(db, final.id)
        subtotal = sum((i.total_price for i in final.line_items), Decimal(0))
        if final.subtotal != subtotal:
            final.subtotal = subtotal
            changed = True
        if "final_total" not in state["overrides"].get("estimate", []):
            total = (
                pre.final_total
                if final.manual_override
                and "manual_override" not in state["overrides"].get("estimate", [])
                else subtotal
            )
            if not final.manual_override or "manual_override" not in state[
                "overrides"
            ].get("estimate", []):
                if final.final_total != total:
                    final.final_total = total
                    changed = True
        valid = {str(i.id) for i in final.images}
        if final.cover_image_id and final.cover_image_id not in valid:
            final.cover_image_id = None
            changed = True
        if changed:
            final.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return final
    finally:
        db.sync_session.info.pop("branch_sync", None)


async def switch_mode(db, estimate, mode):
    if mode not in ("pre", "final"):
        raise ValueError("Unsupported estimate mode")
    # Lock the shared Pre row so two simultaneous first switches create one branch.
    pre = await loaded(db, estimate.source_estimate_id or estimate.id, lock=True)
    db.sync_session.info["branch_sync"] = True
    try:
        if pre.type == "final" and not pre.source_estimate_id:
            original = pre
            pre, state = await clone(db, original, "pre")
            original.source_estimate_id = pre.id
            for kind in MODELS:
                state["maps"][kind] = {v: k for k, v in state["maps"][kind].items()}
            original.branch_state = state
            await db.flush()
        if mode == "pre":
            pre.branch_state = {**(pre.branch_state or {}), "active_mode": "pre"}
            await db.commit()
            return await loaded(db, pre.id)
        final = (
            await db.execute(
                select(Estimate).where(Estimate.source_estimate_id == pre.id)
            )
        ).scalar_one_or_none()
        if not final:
            final, state = await clone(db, pre, "final")
            final.source_estimate_id = pre.id
            final.branch_state = state
            await db.flush()
        pre.branch_state = {**(pre.branch_state or {}), "active_mode": "final"}
        final = await loaded(db, final.id)
        if not final.cover_image_id and final.images:
            final.cover_image_id = str(
                sorted(final.images, key=lambda i: (str(i.zone_id), i.slot))[0].id
            )
    finally:
        db.sync_session.info.pop("branch_sync", None)
    final = await synchronize(db, final)
    await db.commit()
    return await loaded(db, final.id)
