"""Deterministic reference-led Final zone layouts, independent of the old engine.

The approved blank image is a background only. Zone numbers, headings, row
names/prices, separators and totals are native PDF marks. Descriptions and SKU
fields are deliberately excluded from zone slides; source records stay intact.
"""

from dataclasses import dataclass, field
from pathlib import Path
from math import ceil
from PIL import Image, ImageOps
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from .pre_estimate_v1 import _fonts, _wrap
from .final_pricing import key
from .final_zone_photos import PHOTO_REQUIRED

W, H = 1440, 810
X = 82
INK = HexColor("#11110F")
GOLD = HexColor("#B58B54")
MUTED = HexColor("#746D65")
RULE = HexColor("#D8CFC3")
TEMPLATE = (
    Path(__file__).resolve().parents[2] / "assets/proposals/zone-template-clean.png"
)


def money(value):
    return f"${value:,.2f}"


def text(c, value, x, y, size=18, weight="Regular", color=INK, right=False, tracking=0):
    c.setFont("WP-" + weight, size)
    c.setFillColor(color)
    if right:
        c.drawRightString(x, y, str(value))
    else:
        c.drawString(x, y, str(value), charSpace=tracking)


def rule(c, x, y, w, color=RULE, width=0.65):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.line(x, y, x + w, y)


@dataclass(frozen=True)
class Photo:
    path: str
    ident: str
    width: int
    height: int

    @property
    def ratio(self):
        return self.width / self.height


def photos(zone, selected_slot=None, required=True):
    result = []
    if len(getattr(zone, "images", []) or []) > 4:
        raise ValueError(
            "A zone can contain at most 4 photos. Remove extra photos before exporting."
        )
    images = sorted(getattr(zone, "images", []) or [], key=lambda p: p.slot)
    if required and not images:
        raise ValueError(PHOTO_REQUIRED)
    chosen = next(
        (image for image in images if image.slot == selected_slot),
        images[0] if images else None,
    )
    for image in ([chosen] if chosen else []):
        try:
            with Image.open(image.file_path) as source:
                im = ImageOps.exif_transpose(source)
                im.load()
                w, h = im.size
            result.append(Photo(image.file_path, key(image), w, h))
        except (OSError, ValueError) as error:
            raise ValueError(
                "A Final Estimate photo is missing or damaged. Replace or remove it before exporting."
            ) from error
    return result


@dataclass
class Row:
    item: object
    names: list
    price: str
    height: float
    size: float = 19
    lead: float = 27
    continued: bool = False
    price_below: bool = False
    price_offset: float = 0
    price_size: float = 0


@dataclass
class ZonePage:
    zone: object
    number: int
    titles: list
    title_size: float
    rows: list = field(default_factory=list)
    assets: list = field(default_factory=list)
    side: bool = True
    component_y: float = 490
    body_top: float = 440
    body_bottom: float = 100
    columns: int = 1
    part: int = 1
    parts: int = 1
    final: bool = True
    title_only: bool = False
    gallery_only: bool = False
    portrait: bool = False
    text_width: float = 386
    media_box: tuple = (527, 160, 913, 580)
    total_box: tuple = (816, 48, 624, 104)
    sparse: bool = False


# A shared caption clearance applies to every zone. Short scopes receive an
# editorial variant, rather than stretching one small table row across a slide.
COMPONENT_GAP = 60
SHORT_SCOPE_GAPS = {1: 96, 2: 84, 3: 72}


def title_layout(label, width, side):
    label = " ".join(str(label or "Zone").upper().split())
    maximum = 76 if side else 62
    for size in range(maximum, 33, -2):
        # Fit complete words before the paragraph wrapper can split a heading
        # into fragments such as HALLWA / Y.
        if any(
            pdfmetrics.stringWidth(word, "WP-Bold", size) > width
            for word in label.split()
        ):
            continue
        rows = _wrap(label, width, size, "WP-Bold")
        if len(rows) <= 3 and (len(rows) <= 2 or size <= 50):
            return rows, size, []
    # Compact full-width title pages preserve pathological names without
    # shrinking text into unreadability or covering the photographs.
    all_lines = _wrap(label, W - 2 * X, 34, "WP-Bold")
    return (
        _wrap(label, width, 34, "WP-Bold")[:2],
        34,
        [all_lines[n : n + 9] for n in range(0, len(all_lines), 9)],
    )


def geometry(zone, number, assets, continued=False):
    side = bool(assets)
    portrait = bool(assets and assets[0].ratio < 1)
    width = 738 if portrait else 390 if side else W - 2 * X
    titles, size, introductions = title_layout(zone.label, width, side)
    baseline = 620
    last = baseline - (len(titles) - 1) * size * 1.25
    components = last - 64
    top = components - COMPONENT_GAP
    if top < 365:
        size = min(size, 44)
        titles = _wrap(zone.label.upper(), width, size, "WP-Bold")[:3]
        last = baseline - (len(titles) - 1) * size * 1.25
        components = last - 54
        top = components - COMPONENT_GAP
    return (
        ZonePage(
            zone,
            number,
            titles,
            size,
            assets=assets,
            side=side,
            component_y=components,
            body_top=top,
            body_bottom=170 if portrait else 100 if side else 205,
            columns=1 if side else 2,
            portrait=portrait,
            text_width=738 if portrait else 386,
            media_box=(912, 18, 490, 774) if portrait else (527, 160, 913, 580),
            total_box=(82, 44, 738, 104) if portrait else (816, 48, 624, 104),
        ),
        introductions,
    )


def row_data(items, width, capacity, quote, size=19, padding=20, weight="Regular"):
    lead = size + 8
    price_width = max(
        145,
        max(
            (
                pdfmetrics.stringWidth(
                    "To be confirmed" if i.is_tbd else money(quote.item_prices[key(i)]),
                    "WP-Medium",
                    size,
                )
                + 22
                for i in items
            ),
            default=145,
        ),
    )
    name_width = max(125, width - price_width - 24)
    max_lines = max(1, int((capacity - 24) // lead))
    rows = []
    for item in items:
        names = _wrap(item.name, name_width, size, "WP-" + weight)
        for start in range(0, len(names), max_lines):
            part = names[start : start + max_lines]
            rows.append(
                Row(
                    item,
                    part,
                    (
                        (
                            "To be confirmed"
                            if item.is_tbd
                            else money(quote.item_prices[key(item)])
                        )
                        if start == 0
                        else ""
                    ),
                    max(46, len(part) * lead + padding),
                    size,
                    lead,
                    start > 0,
                )
            )
    return rows


def paginate(zone, number, quote, selected_slot=None, photo_required=True):
    assets = photos(zone, selected_slot, required=photo_required)
    base, introductions = geometry(zone, number, assets)
    if introductions and assets:
        title_lines = _wrap(
            " ".join(zone.label.upper().split()), base.text_width, 34, "WP-Bold"
        )
        introductions = [
            title_lines[n : n + 10] for n in range(0, len(title_lines), 10)
        ]
    result = [
        ZonePage(
            zone,
            number,
            t,
            34,
            assets=assets,
            side=bool(assets),
            portrait=base.portrait,
            text_width=base.text_width,
            media_box=base.media_box,
            total_box=base.total_box,
            title_only=True,
        )
        for t in introductions
    ]
    items = sorted(zone.line_items, key=lambda i: i.sort_order)
    remaining = list(items)
    # Name fragments use the same measured width on their continuation; no row
    # is discarded. Source media is strictly limited to four per zone.
    pending = []
    page_index = 0
    while remaining or pending or page_index == 0:
        # Keep the zone's own photographs on continuations, so a short
        # remaining scope keeps the same balanced composition.
        batch = assets
        page, _ = geometry(zone, number, batch, page_index > 0)
        page.sparse = 1 <= len(items) <= 3
        if page.sparse:
            page.body_top = page.component_y - SHORT_SCOPE_GAPS[len(items)]
        width = page.text_width if page.side else (W - 2 * X - 66) / 2
        if not page.side and page.sparse:
            page.columns = 1
            page.text_width = 738
            width = page.text_width
        capacity = page.body_top - page.body_bottom
        if remaining:
            size = (
                (22 if page.side else 26)
                if len(remaining) <= 2
                else 19 if len(remaining) <= 5 else 18
            )
            if page.portrait:
                size = 22 if len(remaining) <= 8 else 20
            if page.sparse:
                size = 28 if len(items) == 1 else 26 if len(items) == 2 else 24
            rows = row_data(
                remaining,
                width,
                capacity,
                quote,
                size,
                padding=16 if not page.sparse and len(items) > 8 else 20,
                weight="Medium" if page.sparse else "Regular",
            )
            if len(items) == 1:
                names = _wrap(items[0].name, width, 30, "WP-Medium")
                offset = (len(names) - 1) * 38 + 58
                if offset + 36 <= capacity:
                    rows = [
                        Row(
                            items[0],
                            names,
                            rows[0].price,
                            offset + 36,
                            size=30,
                            lead=38,
                            price_below=True,
                            price_offset=offset,
                            price_size=36,
                        )
                    ]
            pending += rows
            remaining = []
        target_capacity = capacity * page.columns
        # Do not strand one or two rows on a needless continuation. Balance the
        # remaining measured rows when they genuinely need multiple pages.
        total = sum(r.height for r in pending)
        expected = max(1, ceil(total / target_capacity), ceil(len(pending) / 8))
        target = min(
            target_capacity,
            total / expected + max((r.height for r in pending), default=0) * 0.45,
        )
        selected = []
        used = 0
        while pending:
            row = pending[0]
            if selected and (
                len(selected) >= 8
                or used + row.height > target_capacity
                or (used >= target and len(pending) > 1)
            ):
                break
            if row.height > capacity:
                # Re-split a row when a later, narrower title reduces capacity.
                cut = max(1, int((capacity - 20) // row.lead))
                names = row.names[:cut]
                tail = row.names[cut:]
                if tail:
                    pending.insert(
                        1,
                        Row(
                            row.item,
                            tail,
                            "",
                            len(tail) * row.lead + 20,
                            row.size,
                            row.lead,
                            True,
                        ),
                    )
                row = Row(
                    row.item,
                    names,
                    row.price,
                    len(names) * row.lead + 20,
                    row.size,
                    row.lead,
                    row.continued,
                )
            # Keep each text-first column within its own vertical capacity.
            if page.columns == 2:
                packed = sum(r.height for r in selected if getattr(r, "column", 0) == 0)
                col = (
                    1
                    if any(getattr(r, "column", 0) == 1 for r in selected)
                    or packed + row.height > capacity
                    else 0
                )
                used_col = sum(
                    r.height for r in selected if getattr(r, "column", 0) == col
                )
                if used_col + row.height > capacity and selected:
                    break
                row.column = col
            selected.append(row)
            pending.pop(0)
            used += row.height
        if page.columns == 2 and len(selected) > 1:
            splits = [
                n
                for n in range(1, len(selected))
                if sum(r.height for r in selected[:n]) <= capacity
                and sum(r.height for r in selected[n:]) <= capacity
            ]
            if splits:
                cut = min(
                    splits,
                    key=lambda n: abs(
                        sum(r.height for r in selected[:n])
                        - sum(r.height for r in selected[n:])
                    ),
                )
                for n, row in enumerate(selected):
                    row.column = 0 if n < cut else 1
        page.rows = selected
        page.gallery_only = not selected and bool(batch) and bool(items)
        result.append(page)
        page_index += 1
        if not pending:
            break
    # Photo-only continuation slides carry the total only once, at the end.
    count = len(result)
    for n, p in enumerate(result, 1):
        p.part = n
        p.parts = count
        p.final = n == count
    return result


def contained(c, photo, x, y, w, h):
    with Image.open(photo.path) as source:
        mode = (
            "RGBA"
            if "A" in source.getbands() or "transparency" in source.info
            else "RGB"
        )
        im = ImageOps.exif_transpose(source).convert(mode)
        iw, ih = im.size
        factor = min(w / iw, h / ih)
        dw, dh = iw * factor, ih * factor
        c.drawImage(
            ImageReader(im), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, mask="auto"
        )


def draw_total(c, page, quote):
    x, y, w, h = page.total_box
    c.saveState()
    path = c.beginPath()
    path.rect(x, y, w, h)
    c.clipPath(path, stroke=0, fill=0)
    c.linearGradient(
        x,
        y,
        x + w,
        y,
        [HexColor("#CFA168"), HexColor("#F2DBB6"), HexColor("#DCB98D")],
        [0, 0.5, 1],
    )
    c.restoreState()
    text(c, "TOTAL", x + 64, y + 40, 19, tracking=3)
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.65)
    c.line(x + 194, y + 25, x + 194, y + 79)
    if not page.zone.line_items:
        value = "Review required"
    elif all(i.is_tbd for i in page.zone.line_items):
        value = "To be confirmed"
    else:
        value = money(quote.zone_prices[key(page.zone)])
    size = 50 if value.startswith("$") else 25
    while pdfmetrics.stringWidth(value, "WP-Bold", size) > w - 274 and size > 23:
        size -= 1
    text(c, value, x + w - 46, y + (31 if size > 35 else 42), size, "Bold", right=True)


def draw(c, page, quote):
    try:
        with Image.open(TEMPLATE) as im:
            iw, ih = im.size
            scale = min(W / iw, H / ih)
            c.drawImage(
                ImageReader(im),
                (W - iw * scale) / 2,
                (H - ih * scale) / 2,
                iw * scale,
                ih * scale,
            )
    except (OSError, ValueError) as error:
        raise ValueError(
            "Final Estimate zone template is missing or damaged."
        ) from error
    rule(c, X, 724, 56, GOLD, 3)
    text(c, f"{page.number:02d}" if page.number else "—", 156, 717, 19)
    if page.parts > 1:
        text(c, f"{page.part}/{page.parts}", 420, 719, 13, color=MUTED, right=True)
    if page.assets:
        contained(c, page.assets[0], *page.media_box)
    if page.title_only:
        for n, title in enumerate(page.titles):
            text(c, title, X, 625 - n * 47, 34, "Bold")
        return
    last = 620 - (len(page.titles) - 1) * (page.title_size * 1.25)
    for n, title in enumerate(page.titles):
        color = GOLD if n == len(page.titles) - 1 and len(page.titles) > 1 else INK
        if page.portrait and len(page.titles) == 1 and " " in title:
            prefix, accent = title.rsplit(" ", 1)
            text(c, prefix + " ", X, 620, page.title_size, "Bold")
            offset = pdfmetrics.stringWidth(prefix + " ", "WP-Bold", page.title_size)
            text(c, accent, X + offset, 620, page.title_size, "Bold", GOLD)
            continue
        text(
            c,
            title,
            X,
            620 - n * (page.title_size * 1.25),
            page.title_size,
            "Bold",
            color,
        )
    rule(c, X, last - 23, 98, GOLD, 2.5)
    text(
        c,
        "PROJECT PHOTOS" if page.gallery_only else "PROJECT COMPONENTS",
        X,
        page.component_y,
        17,
        tracking=3,
    )
    if not page.rows and not page.gallery_only:
        text(c, "SCOPE TO BE CONFIRMED", X, page.body_top - 12, 23, "Medium")
        for n, s in enumerate(
            _wrap(
                "Add priced components before issuing this estimate.",
                page.text_width if page.side else 560,
                17,
            )
        ):
            text(c, s, X, page.body_top - 60 - n * 25, 17, color=MUTED)
    used = [0, 0]
    width = (
        page.text_width
        if page.side or page.sparse
        else (W - 2 * X - 66) / 2 if page.columns == 2 else W - 2 * X
    )
    # For small scopes use measured, bounded spacing rather than ghost rows.
    row_count = max(1, len(page.rows))
    natural = sum(r.height for r in page.rows)
    extra = (
        min(
            40 if page.sparse else 30,
            max(0, (page.body_top - page.body_bottom - natural) / row_count),
        )
        if row_count <= 5 and page.columns == 1
        else 0
    )
    for row in page.rows:
        col = getattr(row, "column", 0)
        x = X + col * (width + 66)
        right = x + width
        y = page.body_top - used[col]
        for n, name in enumerate(row.names):
            text(
                c,
                name,
                x,
                y - n * row.lead,
                row.size,
                "Medium" if page.sparse else "Regular",
            )
        if row.price:
            if row.price_below:
                text(c, row.price, x, y - row.price_offset, row.price_size, "Medium")
                rule(c, x, y - row.price_offset - 26, min(width, 520))
            else:
                text(c, row.price, right, y, row.size, "Medium", right=True)
        used[col] += row.height + extra
        # Center the rule in the measured gap between this row and the next.
        # A fixed offset from the next baseline can cross its ascenders.
        if any(
            getattr(r, "column", 0) == col
            for r in page.rows[page.rows.index(row) + 1 :]
        ):
            face = pdfmetrics.getFont("WP-Regular").face
            bottom = (
                y - (len(row.names) - 1) * row.lead + face.descent * row.size / 1000
            )
            next_top = page.body_top - used[col] + face.ascent * row.size / 1000
            rule(c, x, (bottom + next_top) / 2, width)
    if page.final:
        draw_total(c, page, quote)
