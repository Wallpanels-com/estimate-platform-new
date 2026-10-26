"""Per-zone Final image choice, independent of Pre and unrelated layout settings."""

from pathlib import Path
from types import SimpleNamespace as Obj
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
import sys, uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend"))
from app.services.final_zone_photos import selected_slot, select_photo
from app.services.final_zone_layout import photos
from app.api.v1 import estimates
from fastapi import HTTPException
from pydantic import ValidationError


def fixture():
    zone = Obj(id=uuid.uuid4(), images=[Obj(slot=3), Obj(slot=1)])
    other = Obj(id=uuid.uuid4(), images=[Obj(slot=1), Obj(slot=2)])
    est = Obj(
        id=uuid.uuid4(),
        type="final",
        source_estimate_id=None,
        pdf_layout={"other_setting": True},
        zones=[zone, other],
    )
    return est, zone, other


class FinalZonePhotos(TestCase):
    def test_default_choice_is_first_occupied_slot_not_global_cover(self):
        est, zone, _ = fixture()
        est.cover_image_id = "unrelated global cover"
        self.assertEqual(selected_slot(est, zone), 1)
        self.assertEqual(est.pdf_layout, {"other_setting": True})
        zone.images = []
        self.assertIsNone(selected_slot(est, zone))

    def test_independent_zone_selection_preserves_other_settings_and_replacement(self):
        est, zone, other = fixture()
        select_photo(est, zone, 3)
        select_photo(est, other, 2)
        self.assertTrue(est.pdf_layout["other_setting"])
        self.assertEqual(selected_slot(est, zone), 3)
        self.assertEqual(selected_slot(est, other), 2)
        zone.images = [Obj(slot=3, file_path="replacement.jpg"), Obj(slot=1)]
        self.assertEqual(selected_slot(est, zone), 3)
        zone.images = [Obj(slot=1)]
        self.assertEqual(selected_slot(est, zone), 1)
        self.assertEqual(selected_slot(est, other), 2)

    def test_invalid_selection_does_not_change_layout(self):
        est, zone, _ = fixture()
        with self.assertRaisesRegex(ValueError, "existing photo"):
            select_photo(est, zone, 2)
        self.assertEqual(est.pdf_layout, {"other_setting": True})
        for slot in (0, 5, True, "2"):
            with self.assertRaises(ValidationError):
                estimates.ZonePhotoRequest(slot=slot)

    def test_unselected_broken_image_does_not_block_valid_selected_photo(self):
        from PIL import Image
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "chosen.png"
            Image.new("RGB", (80, 160)).save(file)
            zone = Obj(
                images=[
                    Obj(id="chosen", slot=1, file_path=str(file)),
                    Obj(
                        id="broken", slot=2, file_path=str(file.parent / "missing.png")
                    ),
                ]
            )
            self.assertEqual([photo.ident for photo in photos(zone, 1)], ["chosen"])
            with self.assertRaisesRegex(ValueError, "missing or damaged"):
                photos(zone, 2)


class FinalZonePhotoEndpoint(IsolatedAsyncioTestCase):
    async def test_selection_commits_and_changes_pdf_revision(self):
        est, zone, other = fixture()
        user = Obj(name="Local QA", email="local@example.com")
        db = Obj(commit=AsyncMock())
        with patch.object(estimates, "load_estimate", AsyncMock(return_value=est)):
            result = await estimates.set_zone_photo(
                est.id, zone.id, estimates.ZonePhotoRequest(slot=3), db, user
            )
        self.assertIs(result, est)
        self.assertEqual(selected_slot(est, zone), 3)
        self.assertEqual(est.updated_by_name, "Local QA")
        self.assertIsNotNone(est.updated_at)
        db.commit.assert_awaited_once()

    async def test_rejects_pre_foreign_zone_and_unoccupied_slot(self):
        for kind in ("pre", "foreign-zone", "empty-slot"):
            est, zone, _ = fixture()
            if kind == "pre":
                est.type = "pre"
            db = Obj(commit=AsyncMock())
            with patch.object(estimates, "load_estimate", AsyncMock(return_value=est)):
                with self.assertRaises(HTTPException) as raised:
                    await estimates.set_zone_photo(
                        est.id,
                        uuid.uuid4() if kind == "foreign-zone" else zone.id,
                        estimates.ZonePhotoRequest(
                            slot=2 if kind == "empty-slot" else 3
                        ),
                        db,
                        Obj(),
                    )
            self.assertEqual(
                raised.exception.status_code, 404 if kind == "foreign-zone" else 400
            )
            self.assertEqual(est.pdf_layout, {"other_setting": True})
            db.commit.assert_not_awaited()

    async def test_source_refresh_happens_before_selecting_final_zone(self):
        est, zone, _ = fixture()
        est.source_estimate_id = uuid.uuid4()
        db = Obj(commit=AsyncMock())
        with patch.object(
            estimates, "load_estimate", AsyncMock(return_value=est)
        ), patch.object(estimates, "synchronize", AsyncMock(return_value=est)) as sync:
            await estimates.set_zone_photo(
                est.id,
                zone.id,
                estimates.ZonePhotoRequest(slot=3),
                db,
                Obj(name="QA", email="local@example.com"),
            )
        sync.assert_awaited_once_with(db, est)
        self.assertEqual(selected_slot(est, zone), 3)
