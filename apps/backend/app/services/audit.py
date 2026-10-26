"""Record ORM changes in the same transaction as the business write."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from app.models.governance import AuditEvent

TRACKED = {"estimates", "estimate_zones", "line_items", "estimate_images", "voice_files", "pricing_config", "users", "document_versions"}
REDACTED = {"password_hash", "token_version"}


def value(item):
    if isinstance(item, (uuid.UUID, Decimal)):
        return str(item)
    if isinstance(item, (datetime, date)):
        return item.isoformat()
    return item


@event.listens_for(Session, "before_flush")
def audit_changes(session, flush_context, instances):
    actor = session.info.get("actor")
    if not actor:
        return
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        table = getattr(obj, "__tablename__", "")
        if table not in TRACKED:
            continue
        state = inspect(obj)
        action = "create" if obj in session.new else "delete" if obj in session.deleted else "update"
        changes = {}
        for column in state.mapper.column_attrs:
            key = column.key
            history = state.attrs[key].history
            if key in REDACTED:
                if history.has_changes():
                    changes[key] = {"changed": True}
                continue
            if action == "update" and not history.has_changes():
                continue
            current = value(getattr(obj, key))
            changes[key] = {"before": value(history.deleted[0]) if history.deleted else None, "after": current}
        if not changes:
            continue
        if obj.id is None:
            obj.id = uuid.uuid4()
        estimate_id = obj.id if table == "estimates" else getattr(obj, "estimate_id", None)
        session.add(AuditEvent(
            actor_id=actor["id"], actor_name=actor["name"], estimate_id=estimate_id,
            entity=table, entity_id=str(obj.id), action=action, changes=changes,
        ))
