"""Explicit override tracking survives save/revert and all photo mutations."""

import os, sys, uuid
from copy import deepcopy
from pathlib import Path
from decimal import Decimal
from unittest import TestCase
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend"))
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://unused:unused@127.0.0.1:55432/unused"
)
os.environ.setdefault("SECRET_KEY", "unit-tests-only")
from app.core.database import Base
from app.models.user import User
from app.models.estimate import Estimate, EstimateZone, LineItem, EstimateImage
from app.services.estimate_branches import state_empty, photo_key


class FinalOverrideTracking(TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.db.info["branch_sync"] = True
        self.pre = Estimate(
            id=uuid.uuid4(), user_id=uuid.uuid4(), type="pre", subtotal=0, final_total=0
        )
        self.final = Estimate(
            id=uuid.uuid4(),
            user_id=self.pre.user_id,
            type="final",
            source_estimate_id=self.pre.id,
            subtotal=0,
            final_total=0,
            branch_state=state_empty(),
            manual_override=False,
        )
        self.db.add_all([self.pre, self.final])
        self.db.flush()
        self.zone = EstimateZone(
            id=uuid.uuid4(), estimate_id=self.final.id, label="Room"
        )
        self.item = LineItem(
            id=uuid.uuid4(),
            estimate_id=self.final.id,
            name="Panels",
            quantity=2,
            unit_price=100,
            total_price=200,
        )
        self.db.add_all([self.zone, self.item])
        self.db.flush()
        state = state_empty()
        state["maps"]["zones"][str(uuid.uuid4())] = str(self.zone.id)
        state["maps"]["items"][str(uuid.uuid4())] = str(self.item.id)
        self.final.branch_state = state
        self.db.commit()
        self.db.info.pop("branch_sync")

    def test_reverted_value_remains_explicit_override(self):
        self.zone.label = "Final room"
        self.db.commit()
        self.zone.label = "Room"
        self.db.commit()
        self.assertIn("label", self.final.branch_state["overrides"][str(self.zone.id)])
        self.assertNotIn("label", self.pre.branch_state or {})

    def test_derived_line_and_estimate_totals_are_not_locked(self):
        self.item.quantity = 3
        self.item.total_price = 300
        self.final.subtotal = 300
        self.final.final_total = 300
        self.db.commit()
        self.assertIn(
            "quantity", self.final.branch_state["overrides"][str(self.item.id)]
        )
        self.assertNotIn(
            "total_price", self.final.branch_state["overrides"][str(self.item.id)]
        )
        self.assertNotIn(
            "final_total", self.final.branch_state["overrides"].get("estimate", [])
        )
        self.item.total_price = 333
        self.db.commit()
        self.assertIn(
            "total_price", self.final.branch_state["overrides"][str(self.item.id)]
        )

    def test_manual_final_total_remains_protected(self):
        self.final.manual_override = True
        self.final.final_total = 500
        self.db.commit()
        self.assertIn("final_total", self.final.branch_state["overrides"]["estimate"])

    def test_final_photo_addition_and_removal_lock_stable_slot(self):
        photo = EstimateImage(
            id=uuid.uuid4(),
            estimate_id=self.final.id,
            zone_id=self.zone.id,
            slot=2,
            file_path="/qa/photo.png",
        )
        self.db.add(photo)
        self.db.commit()
        self.assertIn(
            photo_key(photo, self.final.branch_state["maps"]["zones"]),
            self.final.branch_state["overrides"],
        )
        source_id = str(uuid.uuid4())
        state = deepcopy(self.final.branch_state)
        state["maps"]["images"][source_id] = str(photo.id)
        self.final.branch_state = state
        self.db.commit()
        self.db.delete(photo)
        self.db.commit()
        self.assertIn(source_id, self.final.branch_state["deleted"]["images"])


class AsyncSessionAdapter:
    """Run inheritance against an isolated SQLite DB without another dependency."""

    def __init__(self, session):
        self.sync_session = session

    def __getattr__(self, name):
        return getattr(self.sync_session, name)

    async def execute(self, statement):
        return self.sync_session.execute(statement)

    async def flush(self):
        self.sync_session.flush()

    async def commit(self):
        self.sync_session.commit()

    async def delete(self, obj):
        self.sync_session.delete(obj)

    async def refresh(self, obj, attributes):
        self.sync_session.refresh(obj, attributes)


class FinalZoneSynchronization(TestCase):
    def test_moved_item_survives_deletion_of_its_original_source_zone(self):
        import asyncio
        from sqlalchemy import delete
        from app.services.estimate_branches import switch_mode, synchronize, loaded

        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.addCleanup(engine.dispose)
        session = Session(engine, expire_on_commit=False)
        self.addCleanup(session.close)
        pre = Estimate(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            type="pre",
            subtotal=100,
            final_total=100,
        )
        one = EstimateZone(id=uuid.uuid4(), estimate_id=pre.id, label="Original room")
        two = EstimateZone(
            id=uuid.uuid4(), estimate_id=pre.id, label="Destination room"
        )
        item = LineItem(
            id=uuid.uuid4(),
            estimate_id=pre.id,
            zone_id=one.id,
            name="Moved scope",
            total_price=100,
        )
        session.add_all([pre, one, two, item])
        session.commit()
        db = AsyncSessionAdapter(session)

        async def verify():
            final = await switch_mode(db, await loaded(db, pre.id), "final")
            final_id = final.id
            item.zone_id = two.id
            session.commit()
            session.execute(delete(EstimateZone).where(EstimateZone.id == one.id))
            session.commit()
            session.expire_all()
            merged = await synchronize(db, await loaded(db, final_id))
            self.assertEqual(len(merged.zones), 1)
            self.assertEqual(merged.zones[0].label, "Destination room")
            self.assertEqual([i.name for i in merged.line_items], ["Moved scope"])
            self.assertEqual(merged.line_items[0].zone_id, merged.zones[0].id)
            self.assertEqual(merged.subtotal, Decimal("100"))
            self.assertEqual(merged.final_total, Decimal("100"))

        asyncio.run(verify())
