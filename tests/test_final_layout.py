"""Final layout invariants: safe geometry, complete pagination, original artwork."""

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as Obj
from unittest import TestCase
from unittest.mock import patch
import io, sys, uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend"))
from pypdf import PdfReader
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from app.services import final_estimate_layout as layout
import tempfile

_DEFAULT_PHOTO_FOLDER = tempfile.TemporaryDirectory(prefix="wallpanels-layout-photo-")
_DEFAULT_PHOTO = Path(_DEFAULT_PHOTO_FOLDER.name) / "zone.png"
Image.new("RGB", (96, 64), "#c9b89d").save(_DEFAULT_PHOTO)


class AuditedCanvas(Canvas):
    records = []
    rules = []
    pictures = []

    def drawString(self, x, y, text, *args, **kwargs):
        face = pdfmetrics.getFont(self._fontname).face
        width = pdfmetrics.stringWidth(text, self._fontname, self._fontsize)
        bottom = y + face.descent * self._fontsize / 1000
        top = y + face.ascent * self._fontsize / 1000
        self.records.append(
            (self.getPageNumber(), x, bottom, x + width, top, str(text))
        )
        super().drawString(x, y, text, *args, **kwargs)

    def drawImage(self, image, x, y, width=None, height=None, **kwargs):
        if (
            width is not None
            and height is not None
            and not (width > 1438 and height > 808)
        ):
            # The summary brand is separate from the zone media.
            if self.getPageNumber() > 1 and not isinstance(image, str):
                self.pictures.append(
                    (self.getPageNumber(), x, y, x + width, y + height)
                )
        return super().drawImage(image, x, y, width=width, height=height, **kwargs)

    def line(self, x1, y1, x2, y2):
        if y1 == y2:
            self.rules.append((self.getPageNumber(), min(x1, x2), y1, max(x1, x2)))
        super().line(x1, y1, x2, y2)


def item(name="Architectural panels", description="Finish and installation", **kwargs):
    values = dict(
        id=uuid.uuid4(),
        zone_id=uuid.uuid4(),
        name=name,
        description=description,
        quantity=Decimal(12),
        unit="SF",
        unit_price=Decimal(75),
        total_price=Decimal(900),
        is_tbd=False,
        section="General",
        sort_order=0,
    )
    values.update(kwargs)
    return Obj(**values)


def zone(label="Living room", count=4, images=None, **kwargs):
    return Obj(
        id=uuid.uuid4(),
        label=label,
        line_items=[item(name=f"Architectural scope {n+1}") for n in range(count)],
        images=(
            images
            if images is not None
            else [Obj(id=uuid.uuid4(), slot=1, file_path=str(_DEFAULT_PHOTO))]
        ),
        sort_order=0,
        notes=None,
        **kwargs,
    )


def estimate(zones):
    return Obj(
        title="Residence — Architectural Finishes",
        client_name="Local review",
        project_name="Residence",
        zones=zones,
        line_items=[i for z in zones for i in z.line_items],
        images=[i for z in zones for i in z.images],
        cover_image_id=None,
        pdf_layout=None,
        markup_pct=0,
        discount_pct=0,
        manual_override=False,
        subtotal=sum((i.total_price for z in zones for i in z.line_items), Decimal(0)),
        final_total=sum(
            (i.total_price for z in zones for i in z.line_items), Decimal(0)
        ),
    )


class FinalLayout(TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)
        layout._fonts()

    def photos(self, count):
        results = []
        for n in range(count):
            p = self.path / f"photo-{n}.png"
            Image.new(
                "RGB",
                [(1600, 900), (700, 1100), (900, 900), (2000, 300)][n % 4],
                "#c9b89d",
            ).save(p)
            results.append(Obj(id=uuid.uuid4(), file_path=str(p), slot=n + 1))
        return results

    def check_geometry(self, est, name):
        AuditedCanvas.records = []
        AuditedCanvas.rules = []
        AuditedCanvas.pictures = []
        with patch.object(layout.canvas, "Canvas", AuditedCanvas):
            layout.generate_final_client(est, self.path / name)
        records = AuditedCanvas.records
        for page, left, bottom, right, top, value in records:
            self.assertGreaterEqual(left, 80, (page, value, left))
            self.assertGreaterEqual(bottom, 30, (page, value, bottom))
            self.assertLessEqual(right, layout.W - 40, (page, value, right))
            self.assertLessEqual(top, layout.H - 60, (page, value, top))
        for n, a in enumerate(records):
            for b in records[n + 1 :]:
                if a[0] != b[0]:
                    continue
                overlap_x = min(a[3], b[3]) - max(a[1], b[1])
                overlap_y = min(a[4], b[4]) - max(a[2], b[2])
                self.assertFalse(overlap_x > 0.8 and overlap_y > 0.8, (a, b))
        for page, left, y, right in AuditedCanvas.rules:
            for tp, tx, bottom, tr, top, value in records:
                if tp != page:
                    continue
                self.assertFalse(
                    bottom + 0.8 < y < top - 0.8 and min(right, tr) - max(left, tx) > 1,
                    ("Separator intersects text", page, value, y, bottom, top),
                )
        for pp, px, py, pr, pt in AuditedCanvas.pictures:
            for page, left, bottom, right, top, value in records:
                if pp == page:
                    self.assertFalse(
                        min(pr, right) - max(px, left) > 0.8
                        and min(pt, top) - max(py, bottom) > 0.8,
                        ("Photo intersects text", value, pp),
                    )
        return PdfReader(self.path / name)

    def test_zero_to_four_photos_four_scope_items_fit_one_zone_page(self):
        for count in range(5):
            with self.subTest(photos=count):
                est = estimate([zone(images=self.photos(count))])
                if count == 0:
                    with self.assertRaisesRegex(ValueError, "at least one photo"):
                        layout.generate_final_client(est, self.path / "no-photo.pdf")
                    self.assertFalse((self.path / "no-photo.pdf").exists())
                    continue
                if est.images:
                    est.cover_image_id = str(est.images[0].id)
                reader = self.check_geometry(est, f"photos-{count}.pdf")
                self.assertEqual(len(reader.pages), 3)  # shared title, zone, summary
                self.assertIn("Architectural scope 4", reader.pages[1].extract_text())

    def test_long_content_complete_without_overlap_or_shrinking_body(self):
        z = zone(
            label="Architectural finishes / concealed doors / custom cabinetry",
            count=0,
            images=self.photos(3),
        )
        z.notes = "Notes retained. " * 80
        z.line_items = [
            item(
                name="Long unbroken " + ("WALLPANEL" * 14),
                description="Specification detail retained. " * 180,
            ),
            item(name="Last scope item", description="Last description"),
        ]
        est = estimate([z])
        before = deepcopy(est)
        reader = self.check_geometry(est, "long.pdf")
        content = " ".join(" ".join(p.extract_text() for p in reader.pages).split())
        for word in ("Specification", "detail"):
            self.assertEqual(content.split().count(word), 0)
        self.assertEqual(content.split().count("retained."), 0)
        self.assertIn("Last scope item", content)
        self.assertEqual(est.title, before.title)
        self.assertEqual(
            est.zones[0].line_items[0].description,
            before.zones[0].line_items[0].description,
        )

    def test_balanced_summaries_for_variable_zone_counts(self):
        for count in (*range(21), 37):
            est = estimate([zone(label=f"Zone {n+1}", count=1) for n in range(count)])
            pages = layout.summary_pages(est.zones)
            page_counts = [sum(map(len, page.entries)) for page in pages]
            expected_pages = max(1, (count + 9) // 10)
            self.assertEqual(len(pages), expected_pages)
            self.assertLessEqual(max(page_counts) - min(page_counts), 1)
            if count == 12:
                self.assertEqual(page_counts, [6, 6])
                self.assertEqual(
                    [[len(c) for c in p.entries] for p in pages], [[3, 3], [3, 3]]
                )
            if count == 15:
                self.assertEqual(page_counts, [8, 7])
            if count == 20:
                self.assertEqual(page_counts, [10, 10])
            for page in pages:
                if 1 <= count <= 3:
                    self.assertEqual([len(c) for c in page.entries], [count])
                    self.assertGreaterEqual(page.name_size, 28)
                    self.assertGreaterEqual(page.price_size, 32)
                else:
                    self.assertLessEqual(
                        abs(len(page.entries[0]) - len(page.entries[1])), 1
                    )
                self.assertLessEqual(
                    sum(entry[3] for entry in page.entries[0]),
                    layout.SUMMARY_CAPACITY + 0.001,
                )
            self.assertEqual(
                sum(len(col) for page in pages for col in page.entries), count
            )
            reader = self.check_geometry(est, f"zones-{count}.pdf")
            summaries = [
                p.extract_text()
                for p in reader.pages
                if "Investment\nsummary" in p.extract_text()
            ]
            self.assertEqual(len(summaries), expected_pages)
            self.assertEqual(sum("GRAND TOTAL" in text for text in summaries), 1)
            self.assertIn("GRAND TOTAL", summaries[-1])
            for summary in summaries:
                self.assertNotIn("PROJECT INVESTMENT", summary)
                self.assertNotIn("FINAL ESTIMATE", summary)

    def test_sparse_summary_long_names_and_large_prices_fit_above_total(self):
        for count in (1, 2, 3):
            zones = [
                zone(
                    label=f"Zone {n+1} — Full-Height Architectural Wall with Integrated Cabinetry and Concealed Doors",
                    count=1,
                )
                for n in range(count)
            ]
            for z in zones:
                z.line_items[0].total_price = Decimal("123456789.45")
            est = estimate(zones)
            pages = layout.summary_pages(zones, layout.price_quote(est))
            self.assertEqual(len(pages), 1)
            self.assertEqual(len(pages[0].entries), 1)
            self.assertGreaterEqual(
                pages[0].top - sum(e[3] for e in pages[0].entries[0]), 180
            )
            self.check_geometry(est, f"sparse-long-{count}.pdf")

    def test_summary_balancing_respects_measured_capacity_and_source_order(self):
        zones = [
            zone(label=(f"Zone {n+1} " + "Architectural finishes " * 9), count=1)
            for n in range(12)
        ]
        pages = layout.summary_pages(zones)
        shown = [
            entry[0].id
            for page in pages
            for column in page.entries
            for entry in column
            if entry[2]
        ]
        self.assertEqual(shown, [z.id for z in zones])
        self.assertGreater(len(pages), 2)
        for page in pages:
            for column in page.entries:
                self.assertLessEqual(
                    sum(entry[3] for entry in column), layout.SUMMARY_CAPACITY + 0.001
                )
        self.check_geometry(estimate(zones), "summary-long-balanced.pdf")

    def test_summary_columns_share_row_heights_for_long_names(self):
        zones = [zone(label=f"Zone {n+1}", count=1) for n in range(20)]
        zones[1].label = "Living Room TV & Fireplace Feature Wall"
        zones[6].label = "Full Height Decorative Wall Panel Installation"
        zones[12].label = (
            "Architectural finishes with concealed doors and integrated cabinetry"
        )
        est = estimate(zones)
        pages = layout.summary_pages(zones, layout.price_quote(est))
        shown = [
            entry[0].id
            for page in pages
            for column in page.entries
            for entry in column
            if entry[2]
        ]
        self.assertEqual(shown, [zone.id for zone in zones])
        for page in pages:
            left, right = page.entries
            self.assertEqual(
                [entry[3] for entry in left[: len(right)]],
                [entry[3] for entry in right],
            )
            self.assertTrue(
                all(
                    sum(entry[3] for entry in column) <= layout.SUMMARY_CAPACITY
                    for column in page.entries
                )
            )

    def test_zone_images_contain_portrait_landscape_panorama(self):
        for ratio, n in [(1.77, 0), (0.63, 1), (6.67, 3)]:
            photos = self.photos(4)
            est = estimate([zone(images=photos)])
            est.pdf_layout = {
                "final_zone_photos": {str(est.zones[0].id): photos[n].slot}
            }
            with patch.object(
                layout.zone_layout, "contained", wraps=layout.zone_layout.contained
            ) as draw:
                self.check_geometry(est, f"cover-{n}.pdf")
                self.assertEqual(len(draw.call_args_list), 1)
                self.assertTrue(
                    any(
                        call.args[1].path == photos[n].file_path
                        and call.args[2] >= layout.M
                        for call in draw.call_args_list
                    )
                )

    def test_missing_selected_media_fails_instead_of_incomplete_final(self):
        z = zone(
            images=[
                Obj(id=uuid.uuid4(), slot=1, file_path=str(self.path / "missing.png"))
            ]
        )
        with self.assertRaisesRegex(ValueError, "missing or damaged"):
            layout.generate_final_client(estimate([z]), self.path / "missing.pdf")

    def test_selected_photo_repeats_on_every_zone_page_including_title_continuations(
        self,
    ):
        for label in ("Living Room", "ARCHITECTURAL " * 65):
            for slot in (1, 2):
                z = zone(label=label, count=15, images=self.photos(2))
                est = estimate([z])
                est.pdf_layout = {"final_zone_photos": {str(z.id): slot}}
                pages = layout.zone_layout.paginate(z, 1, layout.price_quote(est), slot)
                self.assertGreater(len(pages), 1)
                self.assertTrue(
                    all(
                        [p.path for p in page.assets] == [z.images[slot - 1].file_path]
                        for page in pages
                    )
                )
                with patch.object(
                    layout.zone_layout, "contained", wraps=layout.zone_layout.contained
                ) as draw:
                    self.check_geometry(est, f"continuations-{slot}-{len(label)}.pdf")
                    self.assertEqual(len(draw.call_args_list), len(pages))
                    self.assertTrue(
                        all(
                            call.args[1].path == z.images[slot - 1].file_path
                            for call in draw.call_args_list
                        )
                    )

    def test_short_scopes_have_caption_clearance_and_deliberate_composition(self):
        for count in (1, 2, 3):
            for selected in (1, 2):
                with self.subTest(count=count, selected=selected):
                    z = zone(
                        label="Entry Mirror",
                        count=count,
                        images=self.photos(2) if selected else [],
                    )
                    est = estimate([z])
                    if selected:
                        est.pdf_layout = {"final_zone_photos": {str(z.id): selected}}
                    pages = layout.zone_layout.paginate(
                        z, 3, layout.price_quote(est), selected
                    )
                    self.assertEqual(len(pages), 1)
                    page = pages[0]
                    self.assertTrue(page.sparse)
                    self.assertEqual(page.columns, 1)
                    self.assertGreaterEqual(page.component_y - page.body_top, 72)
                    self.assertEqual(len(page.rows), count)
                    self.assertEqual(page.rows[0].price_below, count == 1)
                    self.check_geometry(est, f"short-{count}-{selected}.pdf")

    def test_regular_scopes_share_the_larger_caption_gap(self):
        for selected in (1, 2):
            z = zone(count=9, images=self.photos(2) if selected else [])
            pages = layout.zone_layout.paginate(
                z, 1, layout.price_quote(estimate([z])), selected
            )
            self.assertTrue(all(not page.sparse for page in pages))
            self.assertTrue(
                all(page.component_y - page.body_top == 60 for page in pages)
            )

    def test_portrait_layout_keeps_full_height_photo_and_total_under_scope(self):
        for count in (0, 1, 4, 8, 15):
            z = zone(label="Dining Wall", count=count, images=self.photos(4))
            est = estimate([z])
            est.pdf_layout = {"final_zone_photos": {str(z.id): 2}}
            pages = layout.zone_layout.paginate(
                z, 1, layout.price_quote(est), selected_slot=2
            )
            self.assertTrue(all(page.portrait for page in pages))
            self.assertTrue(all(page.total_box[0] == 82 for page in pages))
            self.assertTrue(all(page.media_box[3] == 774 for page in pages))
            self.assertTrue(
                all(" ".join(page.titles) == "DINING WALL" for page in pages)
            )
            self.assertEqual(
                sum(bool(row.price) for page in pages for row in page.rows), count
            )
            self.check_geometry(est, f"portrait-{count}.pdf")

    def test_shared_title_is_identical_first_page_for_different_projects(self):
        contents = []
        with Image.open(layout.SHARED_TITLE) as original:
            expected = original.convert("RGB")
            for title in ("Residence A", "A completely different project"):
                est = estimate([zone(count=1)])
                est.title = title
                path = self.path / (title + ".pdf")
                layout.generate_final_client(est, path)
                reader = PdfReader(path)
                first = reader.pages[0]
                self.assertEqual(first.extract_text().strip(), "")
                self.assertEqual(len(first.images), 1)
                embedded = first.images[0].image.convert("RGB")
                self.assertEqual(embedded.size, expected.size)
                self.assertEqual(embedded.tobytes(), expected.tobytes())
                self.assertIn(
                    "LIVING ROOM", " ".join(reader.pages[1].extract_text().split())
                )
                self.assertNotIn("PROJECT OVERVIEW", reader.pages[1].extract_text())
                contents.append(first.get_contents().get_data())
        self.assertEqual(contents[0], contents[1])

    def test_missing_shared_title_blocks_final_export(self):
        with patch.object(layout, "SHARED_TITLE", self.path / "missing-title.png"):
            with self.assertRaisesRegex(
                ValueError, "shared Final Estimate cover is missing or damaged"
            ):
                layout.generate_final_client(
                    estimate([zone(count=1)]), self.path / "incomplete.pdf"
                )

    def test_adaptive_rows_and_total_once_for_every_density(self):
        for count in (0, 1, 2, 3, 5, 6, 8, 9, 10, 15, 30):
            for photos in (0, 4):
                z = zone(
                    label="Kitchen & Cabinetry", count=count, images=self.photos(photos)
                )
                est = estimate([z])
                pricing = layout.price_quote(est)
                if photos == 0:
                    with self.assertRaisesRegex(ValueError, "at least one photo"):
                        layout.zone_layout.paginate(z, 7, pricing)
                    continue
                pages = layout.zone_layout.paginate(z, 7, pricing)
                self.assertTrue(pages)
                self.assertEqual(sum(p.final for p in pages), 1)
                self.assertTrue(pages[-1].final)
                self.assertTrue(all(p.number == 7 for p in pages))
                rows = [r for p in pages for r in p.rows]
                self.assertEqual(sum(bool(r.price) for r in rows), count)
                self.assertEqual(
                    {r.item.id for r in rows}, {i.id for i in z.line_items}
                )
                self.assertEqual(
                    {a.ident for p in pages for a in p.assets},
                    {str(z.images[0].id)} if z.images else set(),
                )
                self.assertTrue(all(len(p.assets) <= 1 for p in pages))
                self.assertEqual(
                    [p.part for p in pages], list(range(1, len(pages) + 1))
                )
                self.assertTrue(
                    all(p.rows or p.assets or not count or p.title_only for p in pages)
                )
                for p in pages:
                    for col in range(p.columns):
                        self.assertLessEqual(
                            sum(
                                r.height
                                for r in p.rows
                                if getattr(r, "column", 0) == col
                            ),
                            p.body_top - p.body_bottom + 0.01,
                        )

    def test_dense_scopes_and_pathological_titles_have_safe_geometry(self):
        zones = [
            zone(
                label="Living Room TV & Fireplace Feature Wall",
                count=15,
                images=self.photos(2),
            ),
            zone(
                label="Full Height Decorative Wall Panel Installation",
                count=8,
                images=self.photos(3),
            ),
            zone(label="ARCHITECTURAL " * 65, count=1),
            zone(label="Custom Closet", count=7),
        ]
        zones[0].line_items[
            2
        ].name = "Full height decorative panel installation with concealed mounting and integrated illumination"
        est = estimate(zones)
        reader = self.check_geometry(est, "dense.pdf")
        text = " ".join(p.extract_text() for p in reader.pages)
        self.assertNotIn("Finish and installation", text)
        self.assertEqual(
            text.count("PROJECT COMPONENTS"),
            sum(
                len(layout.zone_layout.paginate(z, n + 1, layout.price_quote(est)))
                for n, z in enumerate(zones)
            )
            - sum(
                p.title_only
                for n, z in enumerate(zones)
                for p in layout.zone_layout.paginate(z, n + 1, layout.price_quote(est))
            ),
        )

    def test_five_images_are_rejected_without_silently_dropping_a_photo(self):
        z = zone(images=self.photos(5))
        with self.assertRaisesRegex(ValueError, "at most 4 photos"):
            layout.generate_final_client(estimate([z]), self.path / "five.pdf")

    def test_normal_headings_never_split_a_word(self):
        for label in ("Hallway", "Bathroom Vanity", "Master Bedroom Accent Wall"):
            z = zone(label=label, count=1, images=self.photos(1))
            p = layout.zone_layout.paginate(z, 1, layout.price_quote(estimate([z])))[0]
            self.assertEqual(" ".join(p.titles), label.upper())
            self.assertTrue(
                all(
                    word in label.upper().split()
                    for line in p.titles
                    for word in line.split()
                )
            )
        z = zone(label="Custom Closet", count=7)
        pages = layout.zone_layout.paginate(z, 1, layout.price_quote(estimate([z])))
        self.assertEqual(sum(len(p.rows) for p in pages), 7)
        self.assertTrue(all(p.columns == 1 and len(p.assets) == 1 for p in pages))
