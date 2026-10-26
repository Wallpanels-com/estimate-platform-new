"""Premium Final client slides. Measured Montserrat text and uncropped media.

Layout planning is independent of canvas painting. Long names, descriptions and
notes are split into bounded continuation blocks; numeric columns have their
own gutters. Corporate pages are appended by final_estimate_service, unchanged.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageOps
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from .pre_estimate_v1 import _fonts, _wrap, number, money, _plain_number
from .pre_estimate_v2 import Asset, gallery_cells
from . import final_zone_layout as zone_layout
from .final_pricing import quote as price_quote, key as price_key

W, H, M = 1440, 810, 100
INK = HexColor("#272521")
MUTED = HexColor("#777067")
GOLD = HexColor("#AA8658")
LINE = HexColor("#DDD3C6")
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "proposals"
LOGO = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "brand"
    / "wallpanels-verona-transparent.png"
)
SHARED_TITLE = ASSETS / "final-shared-title.png"
BOTTOM = 172


def text(c, value, x, y, size=16, weight="Regular", color=INK, right=False):
    c.setFont("WP-" + weight, size)
    c.setFillColor(color)
    (c.drawRightString if right else c.drawString)(x, y, str(value))


def lines(c, values, x, y, size=16, leading=24, weight="Regular", color=INK):
    for value in values:
        text(c, value, x, y, size, weight, color)
        y -= leading
    return y


def line(c, x, y, width):
    c.setStrokeColor(LINE)
    c.setLineWidth(0.7)
    c.line(x, y, x + width, y)


def contained(c, path, x, y, w, h):
    with Image.open(path) as original:
        image = ImageOps.exif_transpose(original).convert("RGBA")
        iw, ih = image.size
        ratio = min(w / iw, h / ih)
        dw, dh = iw * ratio, ih * ratio
        c.drawImage(
            ImageReader(image), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, mask="auto"
        )


def background(c, index):
    path = ASSETS / f"final-background-{0 if index==0 else 1+(index-1)%3}.png"
    if not path.is_file():
        raise ValueError("Final Estimate background is unavailable.")
    contained(c, path, 0, 0, W, H)


def shared_title(c):
    """The same untouched first slide for every Final, with no overlays."""
    try:
        contained(c, SHARED_TITLE, 0, 0, W, H)
    except (OSError, ValueError) as error:
        raise ValueError(
            "The shared Final Estimate cover is missing or damaged. Final Estimate was not generated."
        ) from error


def brand(c):
    c.drawImage(
        str(LOGO),
        W - M - 225,
        H - 92,
        225,
        225 * ImageReader(str(LOGO)).getSize()[1] / ImageReader(str(LOGO)).getSize()[0],
        mask="auto",
    )


def footer(c, index, count):
    text(c, f"{index+1:02d} / {count:02d}", W - M, 54, 11, color=MUTED, right=True)


def amount(value):
    # Keep explicit cents for a final, including zero-value scope.
    return f"${number(value):,.2f}"


def price(item, factor):
    return (
        "To be confirmed"
        if getattr(item, "is_tbd", False)
        else amount(number(item.total_price) * factor)
    )


def zone_total(zone, factor):
    return sum((number(i.total_price) for i in zone.line_items), Decimal(0)) * factor


def media_for(zone):
    result = []
    for photo in sorted(getattr(zone, "images", []) or [], key=lambda i: i.slot):
        try:
            with Image.open(photo.file_path) as original:
                image = ImageOps.exif_transpose(original)
                w, h = image.size
                image.verify() if image is original else None
            result.append(Asset(photo.file_path, str(photo.id), w, h, False))
        except (OSError, ValueError):
            raise ValueError(
                "A Final Estimate photo is missing or damaged. Replace or remove it before exporting."
            )
    return result


@dataclass
class Block:
    content: list
    height: float
    price: str = ""
    detail: str = ""
    kind: str = "item"
    column: int = 0


@dataclass
class Page:
    kind: str
    zone: object = None
    titles: list = field(default_factory=list)
    blocks: list = field(default_factory=list)
    assets: list = field(default_factory=list)
    top: float = 560
    x: float = M
    width: float = W - 2 * M
    continued: bool = False
    last: bool = True
    entries: list = field(default_factory=list)
    mode: str = "side"
    name_size: float = 19
    price_size: float = 21
    leading: float = 26


def split_blocks(
    content, width, kind="note", item=None, factor=Decimal(1), large=False
):
    """Keep all source text; never shrink body below 16 pt or clip a row."""
    values = []
    heading, heading_lead = (26, 36) if large else (19, 27)
    body, body_lead = (18, 28) if large else (16, 24)
    if item:
        values += [
            (s, "Medium", heading, heading_lead, INK)
            for s in _wrap(item.name, width - 12, heading, "WP-Medium")
        ]
        if item.description:
            values += [
                (s, "Regular", body, body_lead, MUTED)
                for s in _wrap(item.description, width - 12, body)
            ]
    else:
        values = [(s, "Regular", 16, 24, MUTED) for s in _wrap(content, width - 12, 16)]
    chunks = []
    chunk = []
    height = 0
    # Every block fits even when a title takes two lines. Split long prose only
    # at measured line boundaries, retaining every line on continuation slides.
    for row in values:
        if height + row[3] > 230 and chunk:
            chunks.append(chunk)
            chunk = []
            height = 0
        chunk.append(row)
        height += row[3]
    if chunk:
        chunks.append(chunk)
    for n, rows in enumerate(chunks):
        detail = ""
        if item and n == 0:
            qty = _plain_number(item.quantity) if item.quantity is not None else "-"
            unit = item.unit or ""
            rate = (
                "To be confirmed"
                if item.is_tbd
                else (
                    amount(number(item.unit_price) * factor)
                    if item.unit_price is not None
                    else "-"
                )
            )
            detail = f"{qty} {unit}  |  Unit price: {rate}"
        detail_lines = _wrap(detail, width + 150, 16 if large else 14) if detail else []
        yield Block(
            rows,
            sum(r[3] for r in rows) + len(detail_lines) * 20 + (18 if detail else 20),
            price(item, factor) if item and n == 0 else "",
            detail_lines,
            kind,
        )


def zone_pages(zone, factor):
    assets = media_for(zone)
    side = bool(assets)
    scope = (
        not side
        and len(zone.line_items) <= 3
        and len(getattr(zone, "notes", None) or "") < 200
        and all(
            len(i.name) < 200 and len(i.description or "") < 200
            for i in zone.line_items
        )
    )
    banner = bool(len(assets) == 1 and assets[0].ratio > 3)
    width = 590 if side else W - 2 * M
    x = 750 if side else M
    if banner:
        x = M
    # Totals use a full-width band, so even large monetary values have safe space.
    name_width = width - max(
        240 if scope else 170,
        max(
            (
                pdfmetrics.stringWidth(
                    price(i, factor), "WP-Medium", 26 if scope else 20
                )
                + 24
                for i in zone.line_items
            ),
            default=170,
        ),
    )
    titles = _wrap(zone.label or "Zone", 1000, 34, "WP-Medium")
    title_rows = titles[:2]
    top = 580 - 42 * (len(title_rows) - 1)
    if banner:
        top -= 200
    pages = []
    p = Page("zone", zone, title_rows, assets=assets[:4], top=top, x=x, width=width)
    p.mode = "banner" if banner else "scope" if scope else "side"
    pages.append(p)
    y = top
    column = 0
    blocks = []
    if len(titles) > 2:
        blocks += list(split_blocks(zone.label, width - 170))
    dims = []
    for field, label in [
        ("wall_width_ft", "Width"),
        ("wall_height_ft", "Height"),
        ("square_footage", "Area"),
        ("linear_footage", "Length"),
    ]:
        v = getattr(zone, field, None)
        if v is not None:
            dims.append(
                f'{label}: {_plain_number(v)} {"SF" if field=="square_footage" else "LF" if field=="linear_footage" else "ft"}'
            )
    if dims:
        blocks += list(split_blocks("  ·  ".join(dims), width - 12, "dimension"))
    if getattr(zone, "notes", None):
        blocks += list(split_blocks(zone.notes, width - 12))
    previous = None
    for item in sorted(zone.line_items, key=lambda i: i.sort_order):
        section = item.section or ""
        if section and section.lower() != "general" and section != previous:
            for s in _wrap(section, width - 12, 14, "WP-Medium"):
                blocks.append(Block([(s, "Medium", 14, 22, GOLD)], 36, kind="section"))
        previous = section
        blocks += list(
            split_blocks("", name_width, item=item, factor=factor, large=scope)
        )
    if not blocks:
        blocks = [Block([("Scope to be confirmed", "Regular", 18, 28, MUTED)], 60)]
    for idx, block in enumerate(blocks):
        reserve = (
            blocks[idx + 1].height
            if block.kind == "section" and idx + 1 < len(blocks)
            else 0
        )
        if y - block.height - reserve < BOTTOM and p.blocks and banner and column == 0:
            column = 1
            y = top
        if y - block.height - reserve < BOTTOM and p.blocks:
            p.last = False
            # Continuations prioritize readable scope over repeatedly duplicating photos.
            p = Page(
                "zone", zone, title_rows, top=top, x=M, width=W - 2 * M, continued=True
            )
            pages.append(p)
            y = top
            column = 0
            banner = False
        block.column = column
        p.blocks.append(block)
        y -= block.height
    # More than four source images can be supported without changing the planner.
    for start in range(4, len(assets), 4):
        pages.append(
            Page(
                "gallery",
                zone,
                title_rows,
                assets=assets[start : start + 4],
                top=top,
                continued=True,
            )
        )
    return pages


SUMMARY_COLUMN = 588
SUMMARY_GAP = 64
SUMMARY_INDEX = 38
SUMMARY_NAME_SIZE = 19
SUMMARY_PRICE_SIZE = 21
SUMMARY_LEADING = 26
SUMMARY_TOP = 552
SUMMARY_CAPACITY = 372
SUMMARY_MAX_ENTRIES = 10


def summary_pages(zones, pricing=None):
    single = 0 < len(zones) <= 3
    column_width = 1040 if single else SUMMARY_COLUMN
    name_size, price_size, leading = (
        (28, 32, 36)
        if single
        else (SUMMARY_NAME_SIZE, SUMMARY_PRICE_SIZE, SUMMARY_LEADING)
    )
    # Reserve a measured numeric gutter before wrapping names. Both columns use
    # the same row tracks, including when one zone name needs an extra line.
    price_width = max(
        210 if single else 154,
        max(
            (
                pdfmetrics.stringWidth(
                    amount(
                        pricing.zone_prices[price_key(z)]
                        if pricing
                        else zone_total(z, 1)
                    ),
                    "WP-Medium",
                    price_size,
                )
                + 24
                for z in zones
            ),
            default=154,
        ),
    )
    name_width = max(
        200, column_width - SUMMARY_INDEX - price_width - (32 if single else 20)
    )
    entries = []
    for zone in zones:
        names = _wrap(zone.label or "Zone", name_width, name_size, "WP-Medium")
        for start in range(0, len(names), 5):
            part = names[start : start + 5]
            entries.append(
                (
                    zone,
                    part,
                    start == 0,
                    max(
                        {1: 156, 2: 132, 3: 112}[len(zones)] if single else 60,
                        len(part) * leading + (32 if single else 18),
                    ),
                )
            )

    def tracks(part):
        split = len(part) if single else (len(part) + 1) // 2
        columns = [part] if single else [part[:split], part[split:]]
        heights = [
            max(column[n][3] if n < len(column) else 0 for column in columns)
            for n in range(split)
        ]
        return [
            [
                (z, names, priced, heights[n])
                for n, (z, names, priced, _) in enumerate(column)
            ]
            for column in columns
        ], sum(heights)

    # Plan the whole summary before painting: filling one page greedily leaves
    # orphaned rows (e.g. 10 + 2). Keep contiguous source order, use the fewest
    # readable pages, then balance their entry counts and measured row heights.
    total = len(entries)
    measured = {
        (start, count): tracks(entries[start : start + count])
        for start in range(total)
        for count in range(1, min(SUMMARY_MAX_ENTRIES, total - start) + 1)
    }
    counts = ()
    for page_count in range(
        (total + SUMMARY_MAX_ENTRIES - 1) // SUMMARY_MAX_ENTRIES, total + 1
    ):
        if not total:
            break

        @lru_cache(None)
        def plan(start, remaining):
            if remaining == 0:
                return (0, 0, ()) if start == total else None
            available = total - start
            low = max(1, available - SUMMARY_MAX_ENTRIES * (remaining - 1))
            high = min(SUMMARY_MAX_ENTRIES, available - remaining + 1)
            best = None
            for count in range(high, low - 1, -1):
                _, height = measured[start, count]
                if height > SUMMARY_CAPACITY:
                    continue
                tail = plan(start + count, remaining - 1)
                if tail is None:
                    continue
                candidate = (
                    (count * page_count - total) ** 2 + tail[0],
                    height**2 + tail[1],
                    (count,) + tail[2],
                )
                if best is None or candidate[:2] < best[:2]:
                    best = candidate
            return best

        result = plan(0, page_count)
        if result is not None:
            counts = result[2]
            break

    pages = []
    start = 0
    for count in counts:
        columns, height = measured[start, count]
        # Short summaries get deliberate breathing room without enlarging type
        # or consuming the reserved Grand Total band on the final page.
        rows = len(columns[0])
        extra = 0 if single else min(30, (SUMMARY_CAPACITY - height) / rows)
        page = Page("summary", titles=["Investment summary"], continued=bool(pages))
        page.x = M + 100 if single else M
        page.width = column_width
        page.top = (
            SUMMARY_TOP - (SUMMARY_CAPACITY - height) / 2 if single else SUMMARY_TOP
        )
        page.name_size, page.price_size, page.leading = name_size, price_size, leading
        page.entries = [
            [
                (z, names, priced, row_height + extra)
                for z, names, priced, row_height in column
            ]
            for column in columns
        ]
        pages.append(page)
        start += count
    return pages or [Page("summary", titles=["Investment summary"], entries=[[], []])]


def cover(c, est):
    selected = next(
        (
            i
            for i in getattr(est, "images", [])
            if str(i.id) == str(getattr(est, "cover_image_id", None))
        ),
        None,
    )
    # Explicit cover selection only. Without photos use intentional typography.
    title = est.title or est.project_name or est.client_name or "Final Estimate"
    ratio = 1
    if selected:
        with Image.open(selected.file_path) as im:
            ratio = im.width / im.height
    panorama = bool(selected and ratio > 2.4)
    width = 1050 if panorama or not selected else 535
    size = 48
    while size > 26 and len(_wrap(title, width, size, "WP-Bold")) * (size + 12) > (
        170 if panorama else 400
    ):
        size -= 2
    title_lines = _wrap(title, width, size, "WP-Bold")
    if len(title_lines) * (size + 12) > (180 if panorama else 450):
        raise ValueError(
            "The estimate title is too long for a cover. Shorten the title before exporting."
        )
    y = min(565, 390 + len(title_lines) * (size + 10) / 2)
    if panorama:
        y = 610
    text(c, "PROJECT OVERVIEW", M, y + 62, 15, "Medium", GOLD)
    y = lines(c, title_lines, M, y, size, size + 12, "Bold")
    # Long client/project names wrap within the same measured text column.
    client = est.client_name or ""
    if client and client != title and not panorama:
        client_lines = _wrap(client, width, 18)
        if len(client_lines) <= 3 and y - len(client_lines) * 26 > 145:
            lines(c, client_lines, M, y - 24, 18, 26, color=MUTED)
    if selected:
        with Image.open(selected.file_path) as im:
            ratio = im.width / im.height
        box = (
            (M, 130, W - 2 * M, 280)
            if panorama
            else (770, 155, 500, 505) if ratio < 0.85 else (705, 210, 635, 420)
        )
        contained(c, selected.file_path, *box)


def gallery(c, assets, x, y, w, h):
    for a, (bx, by, bw, bh) in zip(assets, gallery_cells(assets, w, h)):
        contained(c, a.path, x + bx * w + 7, y + by * h + 7, bw * w - 14, bh * h - 14)


def heading_surface(c):
    # Keep header type clear of the original artwork's vertical gold lines.
    c.setFillColor(Color(1, 1, 1, 0.96))
    c.rect(M - 16, 560, W - 2 * M + 32, 136, stroke=0, fill=1)


def zone_slide(c, page, factor):
    heading_surface(c)
    label = "ZONE OVERVIEW" if not page.continued else "ZONE OVERVIEW / CONTINUED"
    text(c, label, M, 666, 14, "Medium", GOLD)
    lines(c, page.titles, M, 619, 34, 42, "Medium")
    if page.kind == "gallery":
        gallery(c, page.assets, M, 145, W - 2 * M, page.top - 145)
        return
    if page.assets:
        if page.mode == "banner":
            gallery(c, page.assets, M, page.top + 44, W - 2 * M, 160)
        else:
            gallery(c, page.assets, M, 180, 590, page.top - 160)
    x = page.x
    right = x + page.width
    y = page.top
    column = 0
    # A restrained translucent reading surface keeps prices clear of the original
    # background's architectural lines. The supplied artwork stays byte-identical.
    surface_bottom = (
        max(96, page.top - sum(b.height for b in page.blocks) - 95)
        if page.mode == "scope"
        else 96
    )
    c.setFillColor(Color(1, 1, 1, 0.88))
    c.rect(
        x - 16,
        surface_bottom,
        (W - M - x) + 32,
        page.top + 36 - surface_bottom,
        stroke=0,
        fill=1,
    )
    for block in page.blocks:
        if block.column != column:
            column = block.column
            x = M + 650 * column
            right = x + page.width
            y = page.top
        # Continuation blocks retain their original measured width. Full-width layout
        # deliberately leaves breathing room and never expands the text into prices.
        if block.kind == "section":
            c.setFillColor(Color(0.94, 0.92, 0.88, 0.8))
            c.rect(
                x - 10,
                y - block.height + 8,
                page.width + 10,
                block.height,
                stroke=0,
                fill=1,
            )
        if block.price:
            size = (
                18
                if block.price == "To be confirmed" and page.mode == "scope"
                else (
                    15
                    if block.price == "To be confirmed"
                    else 26 if page.mode == "scope" else 20
                )
            )
            text(c, block.price, right, y, size, "Medium", right=True)
        yy = y
        for s, weight, size, leading, color in block.content:
            text(c, s, x, yy, size, weight, color)
            yy -= leading
        if block.detail:
            lines(
                c,
                block.detail,
                x,
                yy - 5,
                16 if page.mode == "scope" else 14,
                20,
                "Regular",
                MUTED,
            )
        y -= block.height
        if block.kind == "item":
            line(c, x, y + (25 if page.mode == "scope" else 20), page.width)
    if page.last:
        if page.mode == "banner":
            x = M
            right = W - M
        subtotal_y = max(143, y - 36) if page.mode == "scope" else 143
        line(c, x, subtotal_y, right - x)
        pending = all(
            getattr(i, "is_tbd", False) for i in page.zone.line_items
        ) and bool(page.zone.line_items)
        text(c, "Zone subtotal", x, subtotal_y - 30, 14, "Medium", MUTED)
        text(
            c,
            "To be confirmed" if pending else amount(zone_total(page.zone, factor)),
            right,
            subtotal_y - 34,
            25,
            "Medium",
            right=True,
        )


def centered_baseline(center, size, weight="Medium"):
    face = pdfmetrics.getFont("WP-" + weight).face
    return center - (face.ascent + face.descent) * size / 2000


def summary_slide(c, page, est, factor, final_page, pricing=None):
    # All content is drawn directly on the shared zone artwork: no white header,
    # table panels, alternating fills, or opaque total card.
    text(c, "Investment", M, 636, 44, "Bold")
    title_x = M + pdfmetrics.stringWidth("Investment ", "WP-Bold", 44)
    text(c, "summary", title_x, 636, 44, "Bold", GOLD)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2.5)
    c.line(M, 609, M + 88, 609)
    ordered = sorted(est.zones, key=lambda z: z.sort_order)
    numbers = {price_key(zone): n + 1 for n, zone in enumerate(ordered)}
    for column, entries in enumerate(page.entries):
        if not entries:
            continue
        x = page.x + (page.width + SUMMARY_GAP) * column
        right = x + page.width
        text(c, "ZONE", x + SUMMARY_INDEX, page.top + 18, 11, "Medium", MUTED)
        text(c, "INVESTMENT", right, page.top + 18, 11, "Medium", MUTED, right=True)
        line(c, x, page.top, page.width)
        top = page.top
        for zone, names, has_price, height in entries:
            center = top - height / 2
            first = (
                centered_baseline(center, page.name_size)
                + (len(names) - 1) * page.leading / 2
            )
            lines(
                c,
                names,
                x + SUMMARY_INDEX,
                first,
                page.name_size,
                page.leading,
                "Medium",
            )
            if has_price:
                zone_number = numbers.get(price_key(zone))
                text(
                    c,
                    f"{zone_number:02d}" if zone_number else "—",
                    x,
                    centered_baseline(center, 12),
                    12,
                    "Medium",
                    GOLD,
                )
                pending = bool(zone.line_items) and all(
                    i.is_tbd for i in zone.line_items
                )
                text(
                    c,
                    (
                        "—"
                        if pending
                        else amount(
                            pricing.zone_prices[price_key(zone)]
                            if pricing
                            else zone_total(zone, factor)
                        )
                    ),
                    right,
                    centered_baseline(center, page.price_size),
                    page.price_size,
                    "Medium",
                    right=True,
                )
            top -= height
            line(c, x, top, page.width)
    if final_page is not None:
        subtotal = sum((zone_total(z, factor) for z in final_page), Decimal(0))
        discount = number(getattr(est, "discount_pct", None))
        total = pricing.grand_total if pricing else subtotal * (1 - discount / 100)
        if not pricing and getattr(est, "manual_override", False):
            total = number(est.final_total) * factor * (1 - discount / 100)
        x, y, width, height = M, 90, W - 2 * M, 78
        c.saveState()
        path = c.beginPath()
        path.rect(x, y, width, height)
        c.clipPath(path, stroke=0, fill=0)
        c.linearGradient(
            x,
            y,
            x + width,
            y,
            [HexColor("#CFA168"), HexColor("#F2DBB6"), HexColor("#DCB98D")],
            [0, 0.5, 1],
        )
        c.restoreState()
        text(c, "GRAND TOTAL", x + 28, 122, 15, "Bold")
        value = amount(total)
        size = 40
        while pdfmetrics.stringWidth(value, "WP-Bold", size) > 480 and size > 24:
            size -= 1
        text(
            c,
            value,
            W - M - 28,
            centered_baseline(129, size, "Bold"),
            size,
            "Bold",
            right=True,
        )
        if pricing and pricing.manual_adjustment:
            text(c, "MANUAL ADJUSTMENT", M + 250, 141, 10, "Medium")
            text(c, amount(pricing.manual_adjustment), M + 250, 117, 16, "Medium")
        elif discount:
            text(
                c, f"DISCOUNT ({_plain_number(discount)}%)", M + 250, 141, 10, "Medium"
            )
            text(
                c,
                "−"
                + amount(pricing.discount if pricing else subtotal * discount / 100),
                M + 250,
                117,
                16,
                "Medium",
            )
        if any(i.is_tbd for z in final_page for i in z.line_items):
            text(
                c,
                "Unpriced scope is excluded. Pricing will be confirmed separately.",
                M,
                74,
                12,
                color=MUTED,
            )


def generate_final_client(est, output_path):
    from .final_zone_photos import selected_slot

    _fonts()
    zones = sorted(list(est.zones), key=lambda z: z.sort_order)
    direct = [i for i in est.line_items if i.zone_id is None]
    if direct:
        zones.append(
            SimpleNamespace(
                label="Additional scope",
                line_items=direct,
                images=[],
                sort_order=len(zones),
            )
        )
    factor = 1 + number(getattr(est, "markup_pct", None)) / 100
    pricing = price_quote(est, zones)
    if pricing.errors:
        raise ValueError(" ".join(pricing.errors))
    pages = [Page("shared-title")]
    for number_index, zone in enumerate(zones, 1):
        pages += zone_layout.paginate(
            zone,
            number_index if getattr(zone, "id", None) else None,
            pricing,
            selected_slot=selected_slot(est, zone),
            # Unassigned additional scope has no physical zone/photo editor.
            photo_required=bool(getattr(zone, "id", None)),
        )
    pages += summary_pages(zones, pricing)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=(W, H), pageCompression=1, invariant=1)
    c.setTitle(est.title or "Final Estimate")
    c.setAuthor("WALLPANELS.COM by VERONA HOME")
    for index, p in enumerate(pages):
        if isinstance(p, Page) and p.kind == "shared-title":
            shared_title(c)
            c.showPage()
            continue
        if isinstance(p, zone_layout.ZonePage):
            zone_layout.draw(c, p, pricing)
            c.showPage()
            continue
        if p.kind == "summary":
            contained(c, zone_layout.TEMPLATE, 0, 0, W, H)
        else:
            background(c, index - 1)
        brand(c)
        if p.kind == "cover":
            cover(c, est)
        elif p.kind in ("zone", "gallery"):
            zone_slide(c, p, factor)
        else:
            summary_slide(
                c, p, est, factor, zones if index == len(pages) - 1 else None, pricing
            )
        footer(c, index, len(pages))
        c.showPage()
    c.save()
    return str(output_path)
