"""Transactional manual-list entry. Reuses line items and transaction audit receipts."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
import hashlib
import uuid
from pydantic import BaseModel, ConfigDict, Field, model_validator
from fastapi import HTTPException
from sqlalchemy import select
from app.models.estimate import Estimate, LineItem
from app.models.governance import AuditEvent
from app.services.page_access import require_any


class ManualRow(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=500)
    section: str = Field(default='General', min_length=1, max_length=120)
    description: str = Field(default='', max_length=5000)
    unit: Literal['ea', 'SF', 'LF'] = 'ea'
    quantity: Decimal | None = Field(default=None, ge=0, le=99999999.99)
    unit_price: Decimal | None = Field(default=None, ge=0, le=9999999999.99)
    total_price: Decimal = Field(ge=0, le=9999999999.99)
    accept_total: bool = False

    @model_validator(mode='after')
    def validate_calculation(self):
        for value in (self.quantity, self.unit_price, self.total_price):
            if value is not None and (not value.is_finite() or value != value.quantize(Decimal('.01'))):
                raise ValueError('Use finite amounts with up to two decimal places.')
        if (self.quantity is None) != (self.unit_price is None):
            raise ValueError('Enter both quantity and unit price, or leave both empty.')
        if self.quantity is not None:
            calculated = (self.quantity * self.unit_price).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            if calculated != self.total_price and not self.accept_total:
                raise ValueError('Confirm the entered total or use quantity × unit price.')
        return self

    def values(self):
        return dict(name=self.name, section=self.section, description=self.description,
                    quantity=self.quantity, unit=self.unit, unit_price=self.unit_price,
                    original_unit_price=self.unit_price, total_price=self.total_price,
                    calc_type=('sf' if self.unit == 'SF' else 'lf' if self.unit == 'LF' else 'manual') if self.quantity is not None else 'fixed', is_tbd=False)


class ManualBatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: uuid.UUID
    zone_id: uuid.UUID
    rows: list[ManualRow] = Field(min_length=1, max_length=200)


async def save_batch(estimate_id, data, user, db, load_estimate, recalc_totals, touch):
    require_any(user, "estimates", "quick_estimate")
    # Lock before checking the receipt: a concurrent retry must see the commit.
    source = (await db.execute(select(Estimate.source_estimate_id).where(Estimate.id == estimate_id))).scalar_one_or_none()
    await db.execute(select(Estimate.id).where(Estimate.id == (source or estimate_id)).with_for_update())
    receipt_id = uuid.uuid5(estimate_id, f'manual-batch:{user.id}:{data.request_id}')
    digest = hashlib.sha256(data.model_dump_json().encode()).hexdigest()
    receipt = await db.get(AuditEvent, receipt_id)
    if receipt:
        if receipt.changes.get('payload_hash') != digest:
            raise HTTPException(409, 'This batch was already saved with different content. Reload the estimate.')
        db.info['revision_checked'] = True  # Replay only; no mutation or stale overwrite.
        return await load_estimate(estimate_id, user, db)
    est = await load_estimate(estimate_id, user, db)
    if est.deleted_at:
        raise HTTPException(409, 'Restore this estimate before editing it.')
    zone = next((z for z in est.zones if z.id == data.zone_id), None)
    if zone is None:
        raise HTTPException(404, 'Zone not found in this estimate.')
    total = sum((r.total_price for r in data.rows), Decimal(0)) + sum((i.total_price for i in est.line_items), Decimal(0))
    if total > Decimal('9999999999.99'):
        raise HTTPException(422, 'Estimate total exceeds the supported amount.')
    start = max((i.sort_order for i in zone.line_items), default=-1) + 1
    for n, row in enumerate(data.rows):
        db.add(LineItem(estimate_id=est.id, zone_id=zone.id, sort_order=start+n, **row.values()))
    db.add(AuditEvent(id=receipt_id, actor_id=user.id, actor_name=user.name or user.email,
                      estimate_id=est.id, entity='manual_batch', entity_id=str(data.request_id),
                      action='create', changes={'payload_hash': digest, 'count': len(data.rows)}))
    await db.flush()
    est = await load_estimate(estimate_id, user, db)
    recalc_totals(est)
    touch(est, user)
    await db.commit()
    return await load_estimate(estimate_id, user, db)
