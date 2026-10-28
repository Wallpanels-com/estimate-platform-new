"""V2: measured, editorial Pre-Estimate slides; no database or pricing writes.

Frozen V1 numeric/text helpers preserve the established monetary rules. Images
are taken only from their zone association. Identical shared architectural plans are
shown once in the introduction without technical image captions.
"""

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import re

from PIL import Image, ImageOps
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from .pre_estimate_v1 import (
    _fonts,
    _item_detail,
    _pending,
    _pending_only,
    _plain_number,
    _wrap,
    _zone_total,
    money,
    number,
)
from .pdf_optimization import contained as _contain

W, H, M = 1152, 648, 64
INK = HexColor("#292724")
MUTED = HexColor("#77716B")
WARM = HexColor("#F7F5F2")
BEIGE = HexColor("#E8DED3")
TAUPE = HexColor("#B8A18A")
LINE = HexColor("#E5E0DA")
WHITE = HexColor("#FFFFFF")
CONTENT_BOTTOM = 160
COLUMN_GAP = 40
COLUMN_WIDTH = (W - 2 * M - COLUMN_GAP) / 2
LIST_TOP, LIST_CAPACITY = 464, 292
SINGLE_COLUMN_ZONE_LIMIT = 5
LIST_MIN_ROW_HEIGHT = 58
BRAND_LOGO = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "brand"
    / "wallpanels-verona-transparent.png"
)


def text(c, value, x, y, size=14, weight="Regular", color=INK, right=False):
    c.setFillColor(color)
    c.setFont("WP-" + weight, size)
    (c.drawRightString if right else c.drawString)(x, y, str(value))


def lines(c, values, x, y, size, leading, weight="Regular", color=INK):
    for value in values:
        text(c, value, x, y, size, weight, color)
        y -= leading
    return y


def rule(c, x, y, width, color=LINE):
    c.setStrokeColor(color)
    c.setLineWidth(0.6)
    c.line(x, y, x + width, y)


def surface(c, x, y, width, height, color=WARM):
    c.setFillColor(color)
    c.rect(x, y, width, height, fill=1, stroke=0)


def brand(c):
    image = ImageReader(str(BRAND_LOGO))
    iw, ih = image.getSize()
    width = 210
    height = width * ih / iw
    c.drawImage(image, W - M - width, H - 24 - height, width, height, mask="auto")


def zone_label(zone):
    """Keep pricing status out of presentation titles; stored names stay intact."""
    return re.sub(
        r"\s*(?:/|\||-)\s*pricing\s+pending\s*$", "", zone.label, flags=re.IGNORECASE
    ).strip()


def list_price(zone, factor):
    return "-" if _pending_only(zone) else money(_zone_total(zone, factor))


def footer(c, est, n, count):
    rule(c, M, 49, W - 2 * M)
    text(c, f"{n:02d} / {count:02d}", W - M, 30, 10.5, color=MUTED, right=True)


@dataclass(frozen=True)
class Asset:
    path: str
    key: str
    width: int
    height: int
    drawing: bool

    @property
    def ratio(self):
        return self.width / self.height

    @property
    def low_resolution(self):
        return self.width < 500 or self.height < 240


class Media:
    """Read-only catalogue: no project-first-image fallback for any zone."""

    def __init__(self, zones):
        self.by_zone = {}
        cache = {}
        for zone in zones:
            assets = []
            for image in sorted(
                getattr(zone, "images", []) or [], key=lambda im: im.slot
            ):
                path = str(getattr(image, "file_path", "") or "")
                if path not in cache:
                    try:
                        with Image.open(path) as original:
                            im = ImageOps.exif_transpose(original).convert("RGB")
                            width, height = im.size
                            sample = im.copy()
                            sample.thumbnail((96, 96))
                            pixels = list(sample.getdata())
                            white = sum(min(p) > 218 for p in pixels) / len(pixels)
                            color = sum(max(p) - min(p) > 45 for p in pixels) / len(
                                pixels
                            )
                        cache[path] = Asset(
                            path,
                            sha256(Path(path).read_bytes()).hexdigest(),
                            width,
                            height,
                            white > 0.58 and color < 0.12,
                        )
                    except (OSError, ValueError, Image.DecompressionBombError):
                        cache[path] = None
                asset = cache[path]
                if asset and asset.key not in {a.key for a in assets}:
                    assets.append(asset)
            self.by_zone[id(zone)] = assets[:4]
        counts = Counter(a.key for assets in self.by_zone.values() for a in assets)
        unique = {a.key: a for assets in self.by_zone.values() for a in assets}
        # A shared architectural plan belongs in the introduction. Reusing an
        # inspiration photo must not remove it from its assigned zone.
        shared = [a for a in unique.values() if a.drawing and counts[a.key] > 1]
        self.cover = shared[:4] or list(unique.values())[:1]
        self.shared = {a.key for a in shared[:4]}
        self.reference_location = "cover"

    def zone(self, zone):
        return [a for a in self.by_zone[id(zone)] if a.key not in self.shared]

    def has_shared(self, zone):
        return any(a.key in self.shared for a in self.by_zone[id(zone)])


def gallery_cells(assets, width, height):
    """Maximise contained image area; mixed ratios never force a crop."""
    n = len(assets)
    if not n:
        return []
    layouts = {
        1: [[(0, 0, 1, 1)]],
        2: [[(0, 0, 0.5, 1), (0.5, 0, 0.5, 1)], [(0, 0.5, 1, 0.5), (0, 0, 1, 0.5)]],
        3: [
            [(0, 0, 0.5, 1), (0.5, 0.5, 0.5, 0.5), (0.5, 0, 0.5, 0.5)],
            [(0, 0.5, 1, 0.5), (0, 0, 0.5, 0.5), (0.5, 0, 0.5, 0.5)],
            [(0, 2 / 3, 1, 1 / 3), (0, 1 / 3, 1, 1 / 3), (0, 0, 1, 1 / 3)],
        ],
        4: [
            [
                (0, 0.5, 0.5, 0.5),
                (0.5, 0.5, 0.5, 0.5),
                (0, 0, 0.5, 0.5),
                (0.5, 0, 0.5, 0.5),
            ],
            [
                (0, 0, 0.25, 1),
                (0.25, 0, 0.25, 1),
                (0.5, 0, 0.25, 1),
                (0.75, 0, 0.25, 1),
            ],
            [
                (0, 0.75, 1, 0.25),
                (0, 0.5, 1, 0.25),
                (0, 0.25, 1, 0.25),
                (0, 0, 1, 0.25),
            ],
        ],
    }[n]

    def score(layout):
        return sum(
            a.width
            * a.height
            * min(
                max(1, bw * width - 20) / a.width, max(1, bh * height - 20) / a.height
            )
            ** 2
            for a, (_, _, bw, bh) in zip(assets, layout)
        )

    return max(layouts, key=score)


def gallery(c, assets, x, y, width, height):
    for asset, (bx, by, bw, bh) in zip(assets, gallery_cells(assets, width, height)):
        left, right = (4 if bx > 0 else 0), (4 if bx + bw < 0.999999 else 0)
        bottom, top = (4 if by > 0 else 0), (4 if by + bh < 0.999999 else 0)
        gx, gy = x + bx * width + left, y + by * height + bottom
        gw, gh = bw * width - left - right, bh * height - bottom - top
        surface(c, gx, gy, gw, gh)
        _contain(c, asset.path, gx + 8, gy + 8, gw - 16, gh - 16)


@dataclass
class Row:
    kind: str
    content: list
    height: float
    price: str = ""
    continued: bool = False
    inline: bool = False


@dataclass
class Page:
    kind: str
    zone: object = None
    titles: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    entries: list = field(default_factory=list)
    continued: bool = False
    final: bool = True
    assets: list = field(default_factory=list)
    mode: str = "text"
    text_x: float = M
    text_width: float = W - 2 * M
    top: float = 456
    media_box: tuple = ()
    cover_size: int = 48
    columns: list = field(default_factory=list)


def zone_geometry(zone, media, titles):
    assets = media.zone(zone)
    top = 466 - 36 * (len(titles) - 1)
    p = Page("zone", zone=zone, titles=titles, top=top, assets=assets)
    if not assets:
        sections = {item.section or "General" for item in zone.line_items}
        # Short scopes need a deliberate composition; dense schedules retain the
        # compact layout so a spacing change does not create extra slides.
        if len(zone.line_items) <= 3 and len(sections) <= 1:
            p.mode = "scope"
            p.text_x = M
            p.text_width = W - 2 * p.text_x
        return p
    single = assets[0] if len(assets) == 1 else None
    if single and single.ratio > 4:
        height = min(142, max(80, (W - 2 * M) / single.ratio + 16))
        p.mode = "banner"
        p.media_box = (M, top - height + 5, W - 2 * M, height)
        p.top = top - height - 32
    else:
        if single and single.ratio < 0.85:
            width = min(340, max(180, (top - 84 + 12) * single.ratio + 24))
        elif single and single.drawing and single.ratio > 1.6:
            width = 568
        else:
            width = 568
        p.mode = "side"
        p.media_box = (M, 84, width, top - 84 + 12)
        p.text_x = M + width + 40
        p.text_width = W - M - p.text_x
    return p


def zone_pages(zone, factor, media):
    title_lines = _wrap(zone_label(zone), W - 2 * M, 30, "WP-Medium")
    pages = []
    while len(title_lines) > 2:
        part, title_lines = title_lines[:5], title_lines[5:]
        pages.append(Page("zone-title", zone=zone, titles=part))
    if pages:
        title_lines = _wrap(zone_label(zone), W - 2 * M, 30, "WP-Medium")[:2]
    prototype = zone_geometry(zone, media, title_lines)
    scope_only = prototype.mode == "scope"
    capacity = prototype.top - (184 if scope_only else CONTENT_BOTTOM)
    page = prototype
    pages.append(page)
    remaining = capacity
    price_gutter = max(
        112,
        pdfmetrics.stringWidth(money(_zone_total(zone, factor)), "WP-Medium", 22) + 20,
    )
    name_width = page.text_width - price_gutter
    grouped = {}
    for item in sorted(zone.line_items, key=lambda it: it.sort_order):
        grouped.setdefault(item.section or "General", []).append(item)

    def new_page():
        nonlocal page, remaining
        page = zone_geometry(zone, media, title_lines)
        page.continued = True
        pages.append(page)
        remaining = capacity

    def put(row):
        nonlocal remaining
        if row.height > remaining:
            new_page()
        page.rows.append(row)
        remaining -= row.height

    for section, items in grouped.items():
        show_section = len(grouped) > 1 or section.strip().lower() not in {
            "general",
            "project components",
        }
        section_price = (
            money(sum((number(i.total_price) for i in items), Decimal(0)) * factor)
            if len(grouped) > 1
            else ""
        )
        header = None
        if show_section:
            sec_lines = _wrap(section, name_width, 14, "WP-Medium")
            max_lines = max(1, int((capacity - 85) // 22))
            for start in range(0, len(sec_lines), max_lines):
                part = sec_lines[start : start + max_lines]
                header = Row(
                    "section",
                    [(s, "Medium", 14, 22, MUTED) for s in part],
                    len(part) * 22 + 10,
                    section_price if start == 0 else "",
                )
                if remaining < header.height + 44:
                    new_page()
                put(header)
            header = (
                Row("section", [("Section continued", "Medium", 14, 22, MUTED)], 32)
                if len(sec_lines) > max_lines
                else header
            )
        for item in items:
            name_size, name_leading = (21, 29) if scope_only else (19, 27)
            detail_size, detail_leading = (17, 24) if scope_only else (15.5, 22)
            content = [
                (s, "Medium", name_size, name_leading, INK)
                for s in _wrap(item.name, name_width, name_size, "WP-Medium")
            ]
            detail = _item_detail(item, factor)
            if getattr(item, "is_tbd", False):
                # Preserve known scope and quantity without repeating the price
                # status in the description, item amount and zone investment.
                detail = item.description or ""
                if item.quantity is not None:
                    quantity = f'{_plain_number(item.quantity)}{" " + item.unit if item.unit else ""}'
                    detail = "  ·  ".join(
                        value for value in (detail, quantity) if value
                    )
            if detail:
                content += [
                    (s, "Regular", detail_size, detail_leading, MUTED)
                    for s in _wrap(detail, name_width, detail_size)
                ]
            value = (
                "-"
                if getattr(item, "is_tbd", False)
                else money(number(item.total_price) * factor)
            )
            # A panoramic image may leave room for short inline details. Text-only
            # zones use stacked descriptions and a shared, measured content block.
            inline = (
                not scope_only
                and page.text_width >= 960
                and len(_wrap(item.name, 400, 19, "WP-Medium")) == 1
                and len(_wrap(detail, page.text_width - 432 - price_gutter, 15.5)) == 1
            )
            if inline:
                content = [(str(item.name), "Medium", 19, 27, INK)]
                if detail:
                    content.append((detail, "Regular", 15.5, 22, MUTED))
            padding = 22 if scope_only else 14
            min_height = (80 if header else 88) if scope_only else 0
            height = (
                44 if inline else max(min_height, sum(s[3] for s in content) + padding)
            )
            if (
                height <= capacity - (header.height if header else 0)
                and height > remaining
            ):
                new_page()
                if header:
                    put(header)
            if inline:
                put(Row("item", content, height, value, inline=True))
                continue
            continuation = False
            while content:
                chunk, used = [], padding
                for line in content:
                    if max(min_height, used + line[3]) > remaining:
                        break
                    chunk.append(line)
                    used += line[3]
                if not chunk:
                    new_page()
                    continue
                put(Row("item", chunk, max(min_height, used), value, continuation))
                value = ""
                continuation = True
                content = content[len(chunk) :]
                if content:
                    new_page()
    if not grouped:
        put(
            Row(
                "item",
                [("Scope and pricing to be confirmed", "Regular", 16, 22, MUTED)],
                54,
            )
        )
    for page in pages:
        if page.mode == "scope":
            # Centre the complete scope + investment composition within the body.
            # Its width and alignment stay stable with one, many or unpriced items.
            content_height = sum(row.height for row in page.rows) + 100
            page.top = min(page.top, (page.top + 84 + content_height) / 2)
    return pages


def list_pages(kind, zones):
    """Count-based overview/summary policy, shared by every estimate.

    1-5 zones: one full-width column. 6-10: two balanced columns.
    More than 10: balanced pages, each with two columns (11 => 6 + 5;
    20 => 10 + 10). Measured text can require more pages, never smaller type.
    """
    column_count = 1 if len(zones) <= SINGLE_COLUMN_ZONE_LIMIT else 2
    name_width = 718 if column_count == 1 else 274
    max_name_lines = int((LIST_CAPACITY - 10) // 24)
    rows = []
    for idx, zone in enumerate(zones, 1):
        name = _wrap(zone_label(zone), name_width, 18, "WP-Medium")
        for offset in range(0, len(name), max_name_lines):
            part = name[offset : offset + max_name_lines]
            rows.append((idx, zone, part, offset == 0, len(part) * 24 + 10))
    if not rows:
        return [Page(kind)]
    # Each row reserves the same height in both columns, including wrapped names.
    # Balance by count, so ten zones always read 01-05 then 06-10.
    row_height = max(LIST_MIN_ROW_HEIGHT, max(row[4] for row in rows))
    rows = [(*row[:4], row_height) for row in rows]
    per_page = column_count * max(1, int(LIST_CAPACITY // row_height))
    page_count = (len(rows) + per_page - 1) // per_page
    count, extra = divmod(len(rows), page_count)
    pages, offset = [], 0
    for n in range(page_count):
        size = count + (n < extra)
        group = rows[offset : offset + size]
        split = (size + column_count - 1) // column_count
        top = LIST_TOP - (LIST_CAPACITY - split * row_height) / 2
        columns = [group[:split], group[split:]] if column_count == 2 else []
        pages.append(
            Page(
                kind,
                columns=columns,
                entries=group if column_count == 1 else [],
                top=top,
                continued=n > 0,
                final=n == page_count - 1,
            )
        )
        offset += size
    return pages


def list_column(c, rows, x, width, y, factor):
    for idx, zone, name, show_price, height in rows:
        if show_price:
            text(c, f"{idx:02d}", x, y, 12, "Medium", MUTED)
        lines(c, name, x + 36, y, 18, 24, "Medium")
        if show_price:
            text(
                c,
                list_price(zone, factor),
                x + width,
                y,
                19,
                "Medium",
                MUTED if _pending_only(zone) else INK,
                right=True,
            )
        rule(c, x, y - height + 23, width)
        y -= height


def column_entries(c, page, factor):
    for col, rows in enumerate(page.columns):
        list_column(
            c,
            rows,
            M + col * (COLUMN_WIDTH + COLUMN_GAP),
            COLUMN_WIDTH,
            page.top,
            factor,
        )


def plan(est, factor, zones, media):
    client = est.client_name or est.title or "Project"
    wrapped = _wrap(client, 480 if media.cover else W - 2 * M, 48, "WP-Medium")
    if len(wrapped) <= 3:
        pages = [Page("cover", titles=wrapped, assets=media.cover)]
    else:
        wrapped = _wrap(client, W - 2 * M, 38, "WP-Medium")
        pages = [
            Page("cover", titles=wrapped[i : i + 4], continued=i > 0, cover_size=38)
            for i in range(0, len(wrapped), 4)
        ]
        if media.cover:
            media.reference_location = "project introduction"
            pages.append(Page("reference", assets=media.cover))
    if (
        est.prepared_by
        and len(
            _wrap(
                f"Prepared by {est.prepared_by}",
                480 if media.cover else W - 2 * M,
                12.5,
            )
        )
        > 2
    ):
        preparer = _wrap(f"Prepared by {est.prepared_by}", W - 2 * M, 16)
        pages += [
            Page("metadata", titles=preparer[i : i + 12])
            for i in range(0, len(preparer), 12)
        ]
    subtitle = est.project_name or "Custom Interior Solution"
    subtitle_lines = _wrap(subtitle, W - 2 * M, 23, "WP-Medium")
    # Preserve arbitrarily long real project names without colliding with metadata.
    if len(subtitle_lines) > 2:
        pages += [
            Page("project-title", titles=subtitle_lines[i : i + 8], continued=i > 0)
            for i in range(0, len(subtitle_lines), 8)
        ]
    pages += list_pages("overview", zones)
    for zone in zones:
        pages += zone_pages(zone, factor, media)
    pages += list_pages("summary", zones)
    return pages


def cover(c, est, page, media):
    has_media = bool(page.assets)
    # The warm surface is confined to the image; the composition stays white.
    if has_media:
        box = (606, 171, 482, 359)
        if len(page.assets) == 1 and page.assets[0].ratio < 0.85:
            width = min(328, max(180, 370 * page.assets[0].ratio + 24))
            box = (W - M - width, 154, width, 386)
        gallery(c, page.assets, *box)
    surface(c, M, 472, 48, 3, TAUPE)
    size = page.cover_size
    bottom = lines(c, page.titles, M, 426, size, 58 if size == 48 else 46, "Medium")
    subtitle_width = 480 if has_media else W - 2 * M
    subtitle = _wrap(
        est.project_name or "Custom Interior Solution", subtitle_width, 20, "WP-Regular"
    )
    if len(subtitle) <= 2:
        lines(c, subtitle, M, bottom - 4, 20, 28, color=MUTED)
    else:
        text(c, "Custom Interior Solution", M, bottom - 4, 20, color=MUTED)
    y = 142
    if est.prepared_by:
        values = _wrap(
            f"Prepared by {est.prepared_by}", 480 if has_media else W - 2 * M, 12.5
        )
        if len(values) > 2:
            values = ["Prepared by: see project details"]
        lines(c, values, M, y, 12.5, 18)
        y -= len(values) * 18 + 10
    if est.estimate_date:
        text(
            c,
            f"{est.estimate_date:%B} {est.estimate_date.day}, {est.estimate_date.year}",
            M,
            y,
            12,
            color=MUTED,
        )


def entries(c, page, factor, start=None):
    list_column(
        c, page.entries, M, W - 2 * M, page.top if start is None else start, factor
    )


def money_block(c, label, value, x, y, width, height, size=30, fill=BEIGE):
    surface(c, x, y, width, height, fill)
    text(c, label, x + 24, y + height - 27, 14, "Medium", MUTED)
    text(c, value, x + 24, y + 22, size, "Medium")


def overview(c, est, page, factor, total, zones):
    text(c, "Project Overview", M, 528, 32, "Medium")
    text(
        c,
        f'{len(zones)} project {"zone" if len(zones)==1 else "zones"}'
        + (" / continued" if page.continued else ""),
        M,
        492,
        13,
        color=MUTED,
    )
    if page.columns:
        column_entries(c, page, factor)
    else:
        entries(c, page, factor)
    pending = any(_pending(z) for z in zones)
    value = "To be confirmed" if total == 0 and pending else money(total)
    money_block(c, "Current Calculation Basis", value, M, 76, W - 2 * M, 88, 31)
    text(
        c,
        (
            "Confirmed scope only"
            if pending
            else "Based on the scope outlined in this proposal"
        ),
        W - M - 24,
        102,
        11,
        color=MUTED,
        right=True,
    )


def zone_slide(c, page, factor, index, count, media):
    zone = page.zone
    text(
        c,
        f"ZONE {index:02d} / {count:02d}"
        + ("  /  CONTINUED" if page.continued else ""),
        M,
        554,
        12,
        "Medium",
        MUTED,
    )
    if page.kind == "zone-title":
        lines(c, page.titles, M, 502, 30, 40, "Medium")
        text(c, "Scope of work follows on the next slide.", M, 109, 13, color=MUTED)
        return
    lines(c, page.titles, M, 512, 30, 36, "Medium")
    if page.assets:
        gallery(c, page.assets, *page.media_box)
    y = page.top
    for row in page.rows:
        if row.kind == "section":
            rule(c, page.text_x, y + 7, page.text_width, TAUPE)
        row_baseline = y - (24 if page.mode == "scope" else 18)
        baseline = row_baseline
        for idx, (value, weight, size, leading, color) in enumerate(row.content):
            x = page.text_x + (432 if row.inline and idx else 0)
            text(c, value, x, baseline, size, weight, color)
            if not row.inline:
                baseline -= leading
        if row.price:
            text(
                c,
                row.price,
                page.text_x + page.text_width,
                row_baseline,
                14 if row.kind == "section" else 22,
                "Medium",
                MUTED if row.kind == "section" else INK,
                right=True,
            )
        y -= row.height
        if row.kind == "item":
            rule(c, page.text_x, y + 9, page.text_width)
    pending = _pending_only(zone)
    if page.mode == "scope":
        block_top = y - 24
        surface(
            c,
            page.text_x,
            block_top - 76,
            page.text_width,
            76,
            WARM if pending else BEIGE,
        )
        text(
            c,
            "Estimated Zone Investment",
            page.text_x + 24,
            block_top - 44,
            14,
            "Medium",
            MUTED,
        )
        text(
            c,
            "To be confirmed" if pending else money(_zone_total(zone, factor)),
            page.text_x + page.text_width - 24,
            block_top - 49,
            24 if pending else 32,
            "Medium",
            right=True,
        )
        return
    # Keep the investment below the scope/prices column. The media column
    # can now extend almost to the footer, rather than stopping at a full-width band.
    block_width = page.text_width
    block_x = page.text_x
    block_top = max(148, y - 14)
    surface(c, block_x, block_top - 76, block_width, 76, WARM if pending else BEIGE)
    text(
        c,
        "Estimated Zone Investment",
        block_x + 24,
        block_top - (44 if block_width >= 600 else 22),
        14,
        "Medium",
        MUTED,
    )
    text(
        c,
        "To be confirmed" if pending else money(_zone_total(zone, factor)),
        W - M - 24,
        block_top - (49 if block_width >= 600 else 60),
        30,
        "Medium",
        right=True,
    )


def summary(c, page, factor, total, pending):
    text(c, "Investment Summary", M, 528, 32, "Medium")
    text(
        c,
        "Your project at a glance" + (" / continued" if page.continued else ""),
        M,
        492,
        13,
        color=MUTED,
    )
    if page.columns:
        column_entries(c, page, factor)
    else:
        entries(c, page, factor)
    if not page.final:
        text(
            c, "Investment summary continues on the next slide.", M, 96, 13, color=MUTED
        )
        return
    unpriced = total == 0 and pending
    money_block(
        c,
        "Current Calculation Basis",
        "To be confirmed" if unpriced else money(total),
        M,
        84,
        COLUMN_WIDTH,
        88,
        32,
        WARM,
    )
    money_block(
        c,
        "Preliminary Investment Range",
        (
            "To be confirmed"
            if unpriced
            else f'{money(total*Decimal("0.90"))} - {money(total*Decimal("1.15"))}'
        ),
        M + COLUMN_WIDTH + COLUMN_GAP,
        84,
        COLUMN_WIDTH,
        88,
        32,
    )
    note = "Preliminary guide, not a contract. Final pricing follows confirmed scope and measurements."
    if pending:
        note += " Unpriced scope is excluded."
    lines(c, _wrap(note, W - 2 * M, 14), M, 62, 14, 20, color=MUTED)


def generate_pre_estimate(est, output_path):
    """Render V2 from the loaded Estimate; never alter data, files or type."""
    _fonts()
    factor = (Decimal(1) + number(getattr(est, "markup_pct", 0)) / 100) * (
        Decimal(1) - number(getattr(est, "discount_pct", 0)) / 100
    )
    zones = sorted(list(getattr(est, "zones", []) or []), key=lambda z: z.sort_order)
    direct = [i for i in getattr(est, "line_items", []) or [] if i.zone_id is None]
    if direct:
        zones.append(
            SimpleNamespace(
                label="Additional scope",
                sort_order=len(zones),
                line_items=direct,
                images=[],
            )
        )
    media = Media(zones)
    total = sum((_zone_total(z, factor) for z in zones), Decimal(0))
    pending = sum(_pending(z) for z in zones)
    pages = plan(est, factor, zones, media)
    if isinstance(output_path, (str, Path)):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        destination = str(output_path)
    else:
        destination = output_path
    c = canvas.Canvas(destination, pagesize=(W, H), pageCompression=1, invariant=1)
    c.setTitle(f'{est.client_name or est.title or "Project"} | Pre-Estimate')
    c.setAuthor(est.prepared_by or "WallPanels")
    c.setSubject("Preliminary interior scope and investment / Design V2")
    for n, page in enumerate(pages, 1):
        surface(c, 0, 0, W, H, WHITE)
        brand(c)
        if page.kind == "cover":
            cover(c, est, page, media)
        elif page.kind == "reference":
            text(c, "Project Reference", M, 528, 32, "Medium")
            gallery(c, page.assets, M, 112, W - 2 * M, 370)
        elif page.kind == "project-title":
            text(c, "PROJECT", M, 536, 11, "Medium", MUTED)
            lines(c, page.titles, M, 492, 23, 32, "Medium")
        elif page.kind == "metadata":
            text(c, "Project Details", M, 528, 32, "Medium")
            lines(c, page.titles, M, 472, 16, 24)
        elif page.kind == "overview":
            overview(c, est, page, factor, total, zones)
        elif page.kind.startswith("zone"):
            zone_slide(c, page, factor, zones.index(page.zone) + 1, len(zones), media)
        else:
            summary(c, page, factor, total, pending)
        footer(c, est, n, len(pages))
        c.showPage()
    c.save()
    return str(output_path) if isinstance(output_path, (str, Path)) else output_path
