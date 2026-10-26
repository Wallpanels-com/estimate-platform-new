"""Display-only arithmetic must reconcile while leaving saved prices untouched."""

from copy import deepcopy
from decimal import Decimal
from unittest import TestCase, IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
import uuid
import test_final_layout as fixtures
from app.services.final_pricing import quote, key
from app.api.v1.files import upload_image
from fastapi import HTTPException


class FinalPricing(TestCase):
    def test_cent_allocation_markup_discount_once_and_saved_prices_unchanged(self):
        z = fixtures.zone(count=3)
        for i in z.line_items:
            i.total_price = Decimal("0.01")
        est = fixtures.estimate([z])
        est.markup_pct = 10
        est.discount_pct = 5
        before = deepcopy(est)
        result = quote(est)
        self.assertEqual(result.factor, Decimal("1.045"))
        self.assertEqual(sum(result.item_prices.values()), result.grand_total)
        self.assertEqual(sum(result.zone_prices.values()), result.grand_total)
        self.assertEqual(result.grand_total, Decimal("0.03"))
        self.assertEqual(est, before)
        self.assertFalse(result.errors)

    def test_fixed_sf_lf_qty_and_manual_use_saved_extended_amounts(self):
        z = fixtures.zone(count=0)
        z.line_items = [
            fixtures.item(name=kind, calc_type=kind, total_price=Decimal("126.37"))
            for kind in ("fixed", "sf", "lf", "qty", "manual")
        ]
        est = fixtures.estimate([z])
        result = quote(est)
        self.assertEqual(result.grand_total, Decimal("631.85"))
        self.assertTrue(
            all(v == Decimal("126.37") for v in result.item_prices.values())
        )
        self.assertTrue(result.warnings)
        self.assertFalse(result.errors)

    def test_manual_project_total_adjustment_is_separate(self):
        est = fixtures.estimate([fixtures.zone(count=2)])
        est.manual_override = True
        est.final_total = Decimal(2000)
        est.markup_pct = 10
        est.discount_pct = 5
        result = quote(est)
        self.assertEqual(result.grand_total, Decimal(2090))
        self.assertEqual(result.manual_adjustment, Decimal(209))
        self.assertEqual(
            result.component_total + result.manual_adjustment, result.grand_total
        )
        self.assertEqual(sum(result.item_prices.values()), result.component_total)

    def test_unpriced_zero_incomplete_and_invalid_totals_are_reported(self):
        z = fixtures.zone(count=0)
        z.line_items = [
            fixtures.item(name="Unpriced", is_tbd=True, total_price=Decimal(0)),
            fixtures.item(name="Zero", total_price=Decimal(0)),
            fixtures.item(name="Missing rate", calc_type="sf", quantity=None),
        ]
        est = fixtures.estimate([z])
        result = quote(est)
        self.assertEqual(len(result.warnings), 4)
        self.assertFalse(result.errors)
        est.subtotal = Decimal(1)
        est.final_total = Decimal(2)
        self.assertEqual(len(quote(est).errors), 2)
        est.markup_pct = Decimal("NaN")
        self.assertIn(
            "Markup or discount is invalid. Review the estimate before exporting.",
            quote(est).errors,
        )

    def test_direct_scope_is_counted_once(self):
        est = fixtures.estimate([fixtures.zone(count=1)])
        direct = fixtures.item(zone_id=None)
        est.line_items.append(direct)
        est.subtotal += direct.total_price
        est.final_total = est.subtotal
        result = quote(est)
        self.assertEqual(len(result.item_prices), 2)
        self.assertEqual(result.grand_total, Decimal(1800))
        self.assertIn(key(direct), result.item_prices)


class PhotoLimit(IsolatedAsyncioTestCase):
    async def test_upload_refuses_fifth_slot_before_any_database_or_file_operation(
        self,
    ):
        db = AsyncMock()
        file = AsyncMock()
        with self.assertRaises(HTTPException) as raised:
            await upload_image(uuid.uuid4(), uuid.uuid4(), 5, file, db, None)
        self.assertEqual(raised.exception.status_code, 400)
        db.execute.assert_not_awaited()
        file.read.assert_not_awaited()


class ExportChecks(IsolatedAsyncioTestCase):
    async def test_missing_zone_photo_blocks_export_and_identifies_the_zone(self):
        from app.api.v1 import pdf
        from types import SimpleNamespace as Obj
        from app.services.final_zone_photos import PHOTO_REQUIRED

        est = fixtures.estimate(
            [fixtures.zone(label="Dining room", count=1, images=[])]
        )
        before = deepcopy(est)
        db = Obj(
            execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: est)),
            commit=AsyncMock(),
        )
        checks = await pdf.final_check(uuid.uuid4(), db, None)
        self.assertIn(PHOTO_REQUIRED, checks["errors"])
        self.assertEqual(checks["missing_photo_zones"], ["Dining room"])
        self.assertEqual(est, before)
        db.commit.assert_not_awaited()

    async def test_live_diagnostics_are_read_only_and_detect_missing_names(self):
        from app.api.v1 import pdf
        from types import SimpleNamespace as Obj

        est = fixtures.estimate([fixtures.zone(count=1)])
        before = deepcopy(est)
        db = Obj(
            execute=AsyncMock(return_value=Obj(scalar_one_or_none=lambda: est)),
            commit=AsyncMock(),
        )
        result = await pdf.final_check(uuid.uuid4(), db, None)
        self.assertEqual(result, {"warnings": [], "errors": []})
        self.assertEqual(est, before)
        db.commit.assert_not_awaited()
        est.zones[0].line_items[0].name = "   "
        result = await pdf.final_check(uuid.uuid4(), db, None)
        self.assertIn(
            "A component has no name. Add its name before exporting.", result["errors"]
        )
