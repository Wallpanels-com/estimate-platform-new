"""V2 content, image ownership and reversible routing contracts."""

from copy import deepcopy
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as Object
from unittest import TestCase
from unittest.mock import Mock, patch
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend"))
from test_export_layouts import example
from app.services import pre_estimate_service as router
from app.services import pre_estimate_v2 as v2


class PreEstimateVersions(TestCase):
    def test_long_zone_names_stay_whole_and_extreme_names_keep_all_text(self):
        v2._fonts()
        zones = [deepcopy(example().zones[0]) for _ in range(11)]
        for n, zone in enumerate(zones, 1):
            zone.label = f"Room {n:02d} - Wall and cabinetry finishes"
        zones[
            0
        ].label += " with coordinated architectural panelling, concealed service access and integrated lighting"
        before = deepcopy(zones)
        for kind in ("overview", "summary"):
            pages = v2.list_pages(kind, zones)
            rows = [
                row
                for page in pages
                for col in (page.columns or [page.entries])
                for row in col
            ]
            self.assertEqual(len(rows), 11)
            self.assertEqual([row[0] for row in rows], list(range(1, 12)))
            self.assertTrue(all(row[3] for row in rows))
            self.assertGreater(len(rows[0][2]), 3)
        self.assertEqual(zones, before)
        zones[0].label = (
            "Architectural panelling and coordinated cabinetry finishes " * 60
        )
        for kind in ("overview", "summary"):
            pages = v2.list_pages(kind, zones)
            rows = [
                row
                for page in pages
                for col in (page.columns or [page.entries])
                for row in col
            ]
            whole = " ".join(line for row in rows if row[0] == 1 for line in row[2])
            self.assertEqual("".join(whole.split()), "".join(zones[0].label.split()))
            self.assertEqual(sum(row[3] for row in rows), 11)

    def test_zone_counts_one_through_twenty_keep_the_expected_grid(self):
        expected = {
            1: [(1,)],
            2: [(2,)],
            3: [(3,)],
            4: [(4,)],
            5: [(5,)],
            6: [(3, 3)],
            7: [(4, 3)],
            8: [(4, 4)],
            9: [(5, 4)],
            10: [(5, 5)],
            11: [(3, 3), (3, 2)],
            12: [(3, 3), (3, 3)],
            13: [(4, 3), (3, 3)],
            14: [(4, 3), (4, 3)],
            15: [(4, 4), (4, 3)],
            16: [(4, 4), (4, 4)],
            17: [(5, 4), (4, 4)],
            18: [(5, 4), (5, 4)],
            19: [(5, 5), (5, 4)],
            20: [(5, 5), (5, 5)],
        }
        v2._fonts()
        base = example().zones[0]
        for count, layout in expected.items():
            zones = [deepcopy(base) for _ in range(count)]
            for n, zone in enumerate(zones, 1):
                zone.label = f"Zone {n:02d} - Wall finishes"
            before = deepcopy(zones)
            for kind in ("overview", "summary"):
                with self.subTest(zones=count, kind=kind):
                    pages = v2.list_pages(kind, zones)
                    groups = [p.columns or [p.entries] for p in pages]
                    self.assertEqual(
                        [tuple(map(len, columns)) for columns in groups], layout
                    )
                    rows = [row for columns in groups for col in columns for row in col]
                    self.assertEqual(
                        [row[0] for row in rows], list(range(1, count + 1))
                    )
                    self.assertEqual(sum(row[3] for row in rows), count)
                    self.assertEqual(
                        [p.final for p in pages], [False] * (len(pages) - 1) + [True]
                    )
                    for page, columns in zip(pages, groups):
                        self.assertEqual(page.kind, kind)
                        self.assertLessEqual(page.top, v2.LIST_TOP)
                        self.assertTrue(
                            all(len({row[4] for row in col}) == 1 for col in columns)
                        )
                        for col in columns:
                            self.assertLessEqual(
                                sum(row[4] for row in col), v2.LIST_CAPACITY
                            )
                            self.assertGreaterEqual(
                                page.top - sum(row[4] for row in col) + 23, 184
                            )
            self.assertEqual(zones, before)

    def test_short_no_photo_scopes_have_clear_prices_and_no_collisions(self):
        from reportlab.pdfbase import pdfmetrics

        v2._fonts()
        for count, pending in ((1, True), (1, False), (3, False)):
            with self.subTest(count=count, pending=pending):
                zone = deepcopy(example().zones[0])
                zone.images = []
                zone.label = "Wall finishes"
                zone.line_items = zone.line_items[:count]
                for item in zone.line_items:
                    item.section = "General"
                if pending:
                    zone.line_items[0].is_tbd = True
                    zone.line_items[0].unit_price = None
                    zone.line_items[0].total_price = 0
                before = deepcopy(zone)
                pages = v2.zone_pages(zone, Decimal(1), v2.Media([zone]))
                self.assertEqual(len(pages), 1)
                c, boxes, rules, font = Mock(), [], [], []
                c.setFont.side_effect = lambda name, size: font.__setitem__(
                    slice(None), [name, size]
                )

                def draw(x, y, value):
                    ascent, descent = pdfmetrics.getAscentDescent(*font)
                    width = pdfmetrics.stringWidth(value, *font)
                    boxes.append((x, y + descent, x + width, y + ascent, value))

                c.drawString.side_effect = draw
                c.drawRightString.side_effect = lambda x, y, value: draw(
                    x - pdfmetrics.stringWidth(value, *font), y, value
                )
                c.line.side_effect = lambda x0, y0, x1, y1: rules.append(
                    (x0, y0, x1, y1)
                )
                v2.zone_slide(c, pages[0], Decimal(1), 1, 1, v2.Media([zone]))
                for j, (left, bottom, right, top, value) in enumerate(boxes):
                    self.assertGreaterEqual(left, v2.M)
                    self.assertLessEqual(right, v2.W - v2.M)
                    self.assertGreater(bottom, 74)
                    for bl, bb, br, bt, other in boxes[j + 1 :]:
                        self.assertFalse(
                            min(right, br) - max(left, bl) > 1
                            and min(top, bt) - max(bottom, bb) > 1,
                            (value, other),
                        )
                    for x0, y0, x1, _ in rules:
                        if min(x1, right) > max(x0, left):
                            self.assertTrue(y0 < bottom - 2 or y0 > top + 2, value)
                printed = " ".join(box[4] for box in boxes)
                self.assertNotIn("TBD", printed)
                if pending:
                    self.assertIn("-", printed)
                    self.assertNotIn("pending", printed.lower())
                    self.assertIn("To be confirmed", printed)
                self.assertEqual(zone, before)

    def test_dense_no_photo_scope_does_not_gain_slides_from_sparse_spacing(self):
        v2._fonts()
        zone = deepcopy(example().zones[0])
        zone.images = []
        item = zone.line_items[0]
        zone.line_items = [deepcopy(item) for _ in range(5)]
        for n, item in enumerate(zone.line_items):
            item.name = f"Measured scope {n + 1}"
            item.description = "Site measured"
            item.section = "General" if n < 4 else "Mirrors"
            item.sort_order = n
        pages = v2.zone_pages(zone, Decimal(1), v2.Media([zone]))
        self.assertEqual(len(pages), 1)
        self.assertEqual(sum(row.kind == "item" for row in pages[0].rows), 5)

    def test_v1_is_the_exact_pre_redesign_snapshot(self):
        snapshots = sorted(
            (ROOT / ".local/backups").glob("pre-estimate-v1-*/manifest.json")
        )
        if not snapshots:
            self.skipTest("Local snapshot not present in this checkout")
        expected = json.loads(snapshots[0].read_text())[
            "apps/backend/app/services/pre_estimate_service.py"
        ]
        self.assertEqual(
            hashlib.sha256(
                (ROOT / "apps/backend/app/services/pre_estimate_v1.py").read_bytes()
            ).hexdigest(),
            expected,
        )

    def test_both_versions_are_selectable(self):
        for version in ("v1", "v2"):
            with self.subTest(version=version), patch.object(
                router, "design_version", return_value=version
            ), patch(
                f"app.services.pre_estimate_{version}.generate_pre_estimate",
                return_value="client.pdf",
            ) as renderer, patch.object(router, "load_company_slides"), patch.object(
                router, "compose_final_pdf", return_value="ok"
            ) as composer:
                self.assertEqual(
                    router.generate_pre_estimate("estimate", "output"), "ok"
                )
                renderer.assert_called_once()
                view, path = renderer.call_args.args
                self.assertEqual(view._estimate, "estimate")
                self.assertEqual(view.markup_pct, 0)
                self.assertEqual(path.name, "client.pdf")
                composer.assert_called_once()

    def test_shared_image_is_not_misrepresented_as_five_zone_photos(self):
        est = example()
        source = str(ROOT / "tests/fixtures/bhupesh-reference.png")
        for zone in est.zones:
            zone.images = [Object(slot=1, file_path=source)]
        media = v2.Media(est.zones)
        self.assertEqual(len(media.cover), 1)
        self.assertTrue(
            all(not media.zone(z) and media.has_shared(z) for z in est.zones)
        )
        self.assertTrue(all(len(z.images) == 1 for z in est.zones))
        est.zones[1].images = []
        media = v2.Media(est.zones)
        self.assertFalse(media.zone(est.zones[1]))
        self.assertFalse(media.has_shared(est.zones[1]))

    def test_unique_zone_reference_never_leaks_into_other_zones(self):
        est = example()
        est.zones[0].images = [
            Object(slot=1, file_path=str(ROOT / "tests/fixtures/bhupesh-reference.png"))
        ]
        media = v2.Media(est.zones)
        self.assertEqual(len(media.zone(est.zones[0])), 1)
        self.assertTrue(all(not media.zone(z) for z in est.zones[1:]))

    def test_long_client_name_keeps_the_shared_reference(self):
        est = example()
        est.client_name = "An unusually long client company name. " * 30
        source = str(ROOT / "tests/fixtures/bhupesh-reference.png")
        for zone in est.zones:
            zone.images = [Object(slot=1, file_path=source)]
        v2._fonts()
        media = v2.Media(est.zones)
        pages = v2.plan(est, Decimal(1), est.zones, media)
        self.assertTrue(
            any(p.kind == "reference" and len(p.assets) == 1 for p in pages)
        )
        self.assertEqual(media.reference_location, "project introduction")

    def test_v2_keeps_all_data_and_supported_text_size(self):
        est = example()
        before = deepcopy(est)
        out = BytesIO()
        v2.generate_pre_estimate(est, out)
        self.assertTrue(out.getvalue().startswith(b"%PDF"))
        from pypdf import PdfReader

        self.assertNotIn(
            "PRELIMINARY PROPOSAL",
            " ".join(p.extract_text() for p in PdfReader(out).pages),
        )
        self.assertEqual(est, before)
        v2._fonts()
        zone = est.zones[0]
        zone.line_items[0].name = "ExtendedUnbrokenScopeName" * 40
        zone.line_items[0].description = "Measured installation and finish. " * 150
        pages = v2.zone_pages(zone, Decimal(1), v2.Media(est.zones))
        self.assertGreater(len(pages), 2)
        complete_text = " ".join(
            line[0] for page in pages for row in page.rows for line in row.content
        )
        self.assertEqual(complete_text.count("Measured installation"), 150)
        self.assertEqual(
            sum(
                bool(row.price)
                for page in pages
                for row in page.rows
                if row.kind == "item"
            ),
            3,
        )
        for page in pages:
            self.assertLessEqual(
                sum(r.height for r in page.rows), page.top - v2.CONTENT_BOTTOM
            )
            self.assertTrue(all(line[2] >= 14 for r in page.rows for line in r.content))

    def test_contain_for_all_aspect_ratios_and_gallery_sizes(self):
        class Recorder:
            def __init__(self):
                self.images = []
                self.surfaces = []

            def setFillColor(self, *args):
                pass

            def rect(self, *args, **kwargs):
                self.surfaces.append(args[:4])

            def drawImage(self, image, x, y, w, h, **kwargs):
                self.images.append((image.getSize(), x, y, w, h))

        from PIL import Image

        with TemporaryDirectory() as tmp:
            assets = []
            for n, (width, height) in enumerate(
                ((900, 400), (300, 700), (500, 500), (120, 60))
            ):
                path = Path(tmp) / f"aspect-{n}.png"
                # Geometry fixtures only; never uploaded as project photos.
                Image.new("RGB", (width, height), "white").save(path)
                assets.append(v2.Asset(str(path), str(n), width, height, False))
            for count in range(1, 5):
                c = Recorder()
                v2.gallery(c, assets[:count], 64, 163, 424, 300)
                self.assertEqual(len(c.images), count)
                self.assertEqual(min(x for x, y, w, h in c.surfaces), 64)
                self.assertEqual(min(y for x, y, w, h in c.surfaces), 163)
                self.assertEqual(max(x + w for x, y, w, h in c.surfaces), 488)
                self.assertEqual(max(y + h for x, y, w, h in c.surfaces), 463)
                for asset, (size, x, y, w, h) in zip(assets, c.images):
                    self.assertEqual(size, (asset.width, asset.height))
                    self.assertAlmostEqual(w / h, asset.ratio)
                    self.assertGreaterEqual(x, 64)
                    self.assertGreaterEqual(y, 163)
                    self.assertLessEqual(x + w, 488)
                    self.assertLessEqual(y + h, 463)

    def test_list_dividers_clear_prices_and_multiline_names(self):
        from reportlab.pdfbase import pdfmetrics

        class Recorder:
            def __init__(self):
                self.boxes = []
                self.rules = []

            def setFillColor(self, *args):
                pass

            def setStrokeColor(self, *args):
                pass

            def setLineWidth(self, *args):
                pass

            def setFont(self, font, size):
                self.font, self.size = font, size

            def drawString(self, x, y, value):
                ascent, descent = pdfmetrics.getAscentDescent(self.font, self.size)
                width = pdfmetrics.stringWidth(value, self.font, self.size)
                self.boxes.append((x, y + descent, x + width, y + ascent, value))

            def drawRightString(self, x, y, value):
                self.drawString(
                    x - pdfmetrics.stringWidth(value, self.font, self.size), y, value
                )

            def line(self, x0, y0, x1, y1):
                self.rules.append((x0, y0, x1, y1))

        v2._fonts()
        est = example()
        zones = [deepcopy(est.zones[n % 5]) for n in range(10)]
        zones[1].label = (
            "An extended project zone with multiple lines of measured cabinetry and architectural wall finishes "
            * 2
        )
        for kind in ("overview", "summary"):
            for page in v2.list_pages(kind, zones):
                c = Recorder()
                if page.columns:
                    v2.column_entries(c, page, Decimal(1))
                    left = [r[1] for r in c.rules if r[0] == v2.M]
                    right = [r[1] for r in c.rules if r[0] > v2.M]
                    shared = min(len(left), len(right))
                    self.assertEqual(left[:shared], right[:shared])
                else:
                    v2.entries(c, page, Decimal(1))
                for x0, y0, x1, _ in c.rules:
                    for left, bottom, right, top, value in c.boxes:
                        if min(x1, right) > max(x0, left):
                            self.assertTrue(y0 < bottom - 2 or y0 > top + 2, value)

    def test_ten_zone_overview_and_summary_each_stay_on_one_readable_slide(self):
        v2._fonts()
        labels = [
            "Living Room - Landscape",
            "Staircase - Portrait",
            "Library - Square Reference",
            "Lounge - Two References",
            "Dining Room - Three References",
            "Studio - Four References & Low Resolution",
            "Hallway - No Photo / Pricing Pending",
            "Feature Wall - Architectural Drawing",
            "Cabinetry and Wall Finishes - No Photo",
            "Terrace - Wide Panoramic Reference",
        ]
        base = example()
        zones = [deepcopy(base.zones[n % 5]) for n in range(10)]
        for zone, label in zip(zones, labels):
            zone.label = label
        for item in zones[6].line_items:
            item.is_tbd = True
            item.total_price = 0
        before = deepcopy(zones)
        for kind in ("overview", "summary"):
            with self.subTest(kind=kind):
                pages = v2.list_pages(kind, zones)
                self.assertEqual(len(pages), 1)
                self.assertEqual(pages[0].kind, kind)
                self.assertEqual(len(pages[0].columns), 2)
                self.assertEqual([len(col) for col in pages[0].columns], [5, 5])
                rows = [row for col in pages[0].columns for row in col]
                self.assertEqual(len({row[4] for row in rows}), 1)
                self.assertEqual([row[1].label for row in rows], labels)
                self.assertEqual(sum(row[3] for row in rows), 10)
                self.assertTrue(
                    all(sum(row[4] for row in col) <= 292 for col in pages[0].columns)
                )
                canvas = Mock()
                v2.column_entries(canvas, pages[0], Decimal(1))
                printed = [
                    args.args[2]
                    for args in canvas.drawString.call_args_list
                    + canvas.drawRightString.call_args_list
                ]
                self.assertNotIn("pricing pending", " ".join(printed).lower())
                self.assertEqual(printed.count("-"), 3)
                if kind == "summary":
                    canvas.reset_mock()
                    v2.summary(canvas, pages[0], Decimal(1), Decimal(25830), 1)
                    blocks = [call.args for call in canvas.rect.call_args_list]
                    self.assertEqual(blocks[0][0], v2.M)
                    self.assertEqual(
                        blocks[1][0], v2.M + v2.COLUMN_WIDTH + v2.COLUMN_GAP
                    )
                    self.assertEqual(
                        [block[2] for block in blocks], [v2.COLUMN_WIDTH] * 2
                    )
        self.assertEqual(zones, before)

    def test_four_references_fit_a_readable_zone_without_extra_slides(self):
        from PIL import Image

        with TemporaryDirectory() as tmp:
            zone = example().zones[0]
            zone.images = []
            for slot, size in enumerate(
                ((1200, 700), (650, 1050), (800, 800), (320, 180)), 1
            ):
                path = Path(tmp) / f"geometry-{slot}.png"
                Image.new("RGB", size, "#d9cbbf").save(path)
                zone.images.append(Object(slot=slot, file_path=str(path)))
            v2._fonts()
            pages = v2.zone_pages(zone, Decimal(1), v2.Media([zone]))
            self.assertEqual(len(pages), 1)
            self.assertEqual(len(pages[0].assets), 4)
            self.assertEqual(sum(r.kind == "item" for r in pages[0].rows), 3)
            self.assertTrue(
                all(line[2] >= 15.5 for r in pages[0].rows for line in r.content)
            )

    def test_reused_photographs_stay_in_their_own_zones(self):
        from PIL import Image

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "photo.png"
            Image.new("RGB", (900, 600), (95, 65, 30)).save(path)
            est = example()
            for zone in est.zones:
                zone.images = [Object(slot=1, file_path=str(path))]
            before = deepcopy(est)
            media = v2.Media(est.zones)
            self.assertEqual(len(media.cover), 1)
            self.assertFalse(media.shared)
            self.assertTrue(all(len(media.zone(z)) == 1 for z in est.zones))
            self.assertTrue(all(not media.has_shared(z) for z in est.zones))
            self.assertEqual(est, before)

    def test_generic_section_labels_use_the_same_layout_for_every_project(self):
        v2._fonts()
        z = deepcopy(example().zones[0])
        z.images = []
        plans = []
        for section in ("General", "Project components"):
            for item in z.line_items:
                item.section = section
            plans.append(v2.zone_pages(z, Decimal(1), v2.Media([z])))
        self.assertEqual(plans[0], plans[1])
        self.assertTrue(all(row.kind == "item" for p in plans[1] for row in p.rows))
        z.line_items[0].section = "Materials"
        z.line_items[1].section = "Services"
        pages = v2.zone_pages(z, Decimal(1), v2.Media([z]))
        self.assertGreaterEqual(
            sum(row.kind == "section" for p in pages for row in p.rows), 2
        )

    def test_pre_export_bytes_are_stable_for_one_snapshot(self):
        a, b = BytesIO(), BytesIO()
        est = example()
        v2.generate_pre_estimate(est, a)
        v2.generate_pre_estimate(est, b)
        self.assertEqual(a.getvalue(), b.getvalue())
