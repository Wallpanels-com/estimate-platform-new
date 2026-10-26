"""Client-facing 16:9 Pre-Estimate proposals. No writes to the Estimate or pricing.

The original Final PDF renderer remains in pdf_service.py. This renderer uses
vector Montserrat text, measured pagination and contained (never cropped) images.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from threading import Lock
import os

from PIL import Image, ImageOps
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

W, H = 1152, 648
M = 56
INK, MUTED, LINE, PAPER, ACCENT = map(
    HexColor, ("#252522", "#74766f", "#dedfd8", "#f3f3ef", "#96794d")
)
FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT_LOCK = Lock()


def _fonts():
    with FONT_LOCK:
        for weight in ("Regular", "Medium", "Bold"):
            name = "WP-" + weight
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(
                    TTFont(name, str(FONTS / f"Montserrat-{weight}.ttf"))
                )


def number(value):
    return Decimal(str(value or 0))


def money(value):
    v = number(value)
    return f"${v:,.0f}" if v == v.to_integral_value() else f"${v:,.2f}"


def _plain_number(value):
    return (
        f"{number(value):f}".rstrip("0").rstrip(".")
        if "." in f"{number(value):f}"
        else str(number(value))
    )


def _wrap(text, width, size=14, font="WP-Regular"):
    """Measured lines, including unbroken names and deliberate paragraph breaks."""
    result = []
    for paragraph in str(text or "").split("\n"):
        line = ""
        for word in paragraph.split():
            if pdfmetrics.stringWidth(word, font, size) > width:
                if line:
                    result.append(line)
                    line = ""
                fragment = ""
                for char in word:
                    if (
                        fragment
                        and pdfmetrics.stringWidth(fragment + char, font, size) > width
                    ):
                        result.append(fragment)
                        fragment = ""
                    fragment += char
                line = fragment
            elif line and pdfmetrics.stringWidth(line + " " + word, font, size) > width:
                result.append(line)
                line = word
            else:
                line = (line + " " + word).strip()
        result.append(line)
    return result or [""]


def _text(c, text, x, y, size=14, font="WP-Regular", color=INK):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawString(x, y, str(text))


def _right(c, text, x, y, size=14, font="WP-Regular", color=INK):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawRightString(x, y, str(text))


def _paragraph(c, text, x, y, width, size=14, leading=21, font="WP-Regular", color=INK):
    for line in _wrap(text, width, size, font):
        _text(c, line, x, y, size, font, color)
        y -= leading
    return y


def _brand(c, x=M, y=H - 43, small=False):
    # Same typographic brand as the existing generator; no UI tile icon.
    _text(c, "WALLPANELS.COM", x, y, 17 if small else 22, "WP-Bold")
    _text(c, "By VERONA HOME", x, y - 17, 9 if small else 10, "WP-Regular", MUTED)


def _rule(c, x, y, width):
    c.setStrokeColor(LINE)
    c.setLineWidth(0.7)
    c.line(x, y, x + width, y)


def _photo_paths(zone):
    result = []
    for image in sorted(getattr(zone, "images", []) or [], key=lambda p: p.slot):
        path = getattr(image, "file_path", "")
        try:
            with Image.open(path) as im:
                im.verify()
            result.append(path)
        except (OSError, ValueError):
            continue
    return result[:4]


def _contain(c, path, x, y, w, h):
    with Image.open(path) as original:
        im = ImageOps.exif_transpose(original).convert("RGBA")
        scale = min(w / im.width, h / im.height)
        dw, dh = im.width * scale, im.height * scale
        c.drawImage(
            ImageReader(im), x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, mask="auto"
        )


def _gallery(c, paths, x, y, w, h):
    """Choose rows/columns by visible image area, preserving slot order and ratio."""
    n = len(paths)
    if not n:
        return
    layouts = {
        1: [[(0, 0, 1, 1)]],
        2: [[(0, 0, 0.5, 1), (0.5, 0, 0.5, 1)], [(0, 0.5, 1, 0.5), (0, 0, 1, 0.5)]],
        3: [
            [(0, 0, 0.5, 1), (0.5, 0.5, 0.5, 0.5), (0.5, 0, 0.5, 0.5)],
            [(0, 0.5, 0.5, 0.5), (0.5, 0.5, 0.5, 0.5), (0, 0, 1, 0.5)],
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
                (0, 0.75, 1, 0.25),
                (0, 0.5, 1, 0.25),
                (0, 0.25, 1, 0.25),
                (0, 0, 1, 0.25),
            ],
        ],
    }[n]
    sizes = []
    for path in paths:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            sizes.append(im.size)

    def score(layout):
        return sum(
            iw * ih * min(max(1, bw * w - 24) / iw, max(1, bh * h - 24) / ih) ** 2
            for (_, _, bw, bh), (iw, ih) in zip(layout, sizes)
        )

    layout = max(layouts, key=score)
    for path, (bx, by, bw, bh) in zip(paths, layout):
        px, py, pw, ph = x + bx * w + 3, y + by * h + 3, bw * w - 6, bh * h - 6
        c.setFillColor(HexColor("#ffffff"))
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.rect(px, py, pw, ph, fill=1, stroke=1)
        _contain(c, path, px + 10, py + 10, pw - 20, ph - 20)


def _zone_total(zone, factor):
    return sum((number(i.total_price) for i in zone.line_items), Decimal(0)) * factor


def _pending(zone):
    return not zone.line_items or any(
        getattr(i, "is_tbd", False) for i in zone.line_items
    )


def _pending_only(zone):
    return _pending(zone) and all(number(i.total_price) == 0 for i in zone.line_items)


def _item_detail(item, factor=Decimal(1)):
    bits = []
    if item.description:
        bits.append(item.description)
    if getattr(item, "is_tbd", False):
        bits.append("Pricing to be confirmed")
    elif (
        item.calc_type in ("fixed", "manual")
        and item.quantity in (None, 1)
        and (item.unit in ("ea", None))
    ):
        bits.append("Fixed amount")
    elif item.quantity is not None and item.unit_price is not None:
        bits.append(
            f'{_plain_number(item.quantity)}{" "+item.unit if item.unit else ""} × {money(number(item.unit_price)*factor)}'
        )
    return "  ·  ".join(bits)


@dataclass
class Row:
    kind: str
    lines: list
    height: float
    price: str = ""


@dataclass
class Page:
    kind: str
    zone: object = None
    rows: list = field(default_factory=list)
    continued: bool = False
    zones: list = field(default_factory=list)
    final: bool = True
    title_lines: list = field(default_factory=list)


def _zone_pages(zone, factor):
    paths = _photo_paths(zone)
    width = 560 if paths else W - 2 * M
    text_width = width - 135
    title_lines = _wrap(zone.label, W - 2 * M, 30, "WP-Medium")
    # Excessively long zone names receive their own title continuation slides.
    pages = []
    while len(title_lines) > 3:
        pages.append(Page("zone-title", zone=zone, title_lines=title_lines[:3]))
        title_lines = title_lines[3:]
    top = 480 - (len(title_lines) - 1) * 36
    capacity = top - 143
    page = Page("zone", zone=zone, title_lines=title_lines)
    pages.append(page)
    remaining = capacity
    items = sorted(zone.line_items, key=lambda i: i.sort_order)
    groups = {}
    for item in items:
        groups.setdefault(item.section or "General", []).append(item)

    def new_page():
        nonlocal page, remaining
        page = Page("zone", zone=zone, continued=True, title_lines=title_lines)
        pages.append(page)
        remaining = capacity

    for section, group in groups.items():
        sec_lines = [
            (t, "WP-Medium", 11, 16, MUTED)
            for t in _wrap(section, text_width, 11, "WP-Medium")
        ]
        header = Row(
            "section",
            sec_lines,
            len(sec_lines) * 16 + 12,
            (
                money(sum((number(i.total_price) for i in group), Decimal(0)) * factor)
                if len(groups) > 1
                else ""
            ),
        )
        max_header_lines = max(1, int((capacity - 76) // 16))
        for offset in range(0, len(sec_lines), max_header_lines):
            part = sec_lines[offset : offset + max_header_lines]
            section_row = Row(
                "section",
                part,
                len(part) * 16 + 12,
                header.price if offset == 0 else "",
            )
            if remaining < section_row.height + 64:
                new_page()
            page.rows.append(section_row)
            remaining -= section_row.height
        if header.height > capacity - 64:
            header = Row(
                "section", [("Section continued", "WP-Medium", 11, 16, MUTED)], 28
            )
        for item in group:
            lines = [
                (t, "WP-Medium", 15, 21, INK)
                for t in _wrap(item.name, text_width, 15, "WP-Medium")
            ]
            lines += (
                [
                    (t, "WP-Regular", 11.5, 17, MUTED)
                    for t in _wrap(_item_detail(item, factor), text_width, 11.5)
                ]
                if _item_detail(item, factor)
                else []
            )
            height = sum(line[3] for line in lines) + 15
            price = (
                "TBD"
                if getattr(item, "is_tbd", False)
                else money(number(item.total_price) * factor)
            )
            if height <= capacity - header.height and height > remaining:
                new_page()
                page.rows.append(header)
                remaining -= header.height
            while lines:
                take = []
                used = 15
                for line in lines:
                    if used + line[3] > remaining:
                        break
                    take.append(line)
                    used += line[3]
                if not take:
                    new_page()
                    continue
                page.rows.append(Row("item", take, used, price))
                price = ""
                remaining -= used
                lines = lines[len(take) :]
                if lines:
                    new_page()
    if not items:
        page.rows.append(
            Row(
                "item",
                [("Scope and pricing to be confirmed", "WP-Regular", 14, 22, MUTED)],
                50,
            )
        )
    return pages


def _footer(c, est, page_number, page_count):
    _rule(c, M, 49, W - 2 * M)
    client = str(est.client_name or est.title or "Project")
    _text(c, _wrap(client, 550, 9)[0], M, 31, 9, color=MUTED)
    _right(
        c,
        f"Pre-Estimate   /   {page_number:02d} — {page_count:02d}",
        W - M,
        31,
        9,
        color=MUTED,
    )


def _cover(c, est, paths, page):
    _brand(c, y=H - 60)
    c.setFillColor(ACCENT)
    long_title = bool(page.title_lines)
    c.rect(M, 500 if long_title else 425, 42, 3, fill=1, stroke=0)
    _text(
        c,
        "PRE-ESTIMATE" + (" / continued" if page.continued else ""),
        M,
        470 if long_title else 392,
        12,
        "WP-Medium",
        MUTED,
    )
    y = _paragraph(
        c,
        (
            "\n".join(page.title_lines)
            if long_title
            else est.client_name or est.title or "Project"
        ),
        M,
        430 if long_title else 335,
        W - 2 * M if long_title else 470,
        32 if long_title else 48,
        40 if long_title else 58,
        "WP-Medium",
    )
    _text(c, "Custom Interior Solution", M, y - 2, 19)
    if paths and not long_title:
        c.setFillColor(PAPER)
        c.rect(570, 177, 526, 328, fill=1, stroke=0)
        _gallery(c, paths[:1], 582, 189, 502, 304)
        _text(c, "Project reference", 582, 158, 10, color=MUTED)
    elif not long_title:
        # Text-led architecture; no fake photo or empty placeholder frame.
        c.setStrokeColor(LINE)
        c.setLineWidth(1)
        for x, y0, y1 in [(670, 184, 505), (710, 184, 505), (1008, 184, 505)]:
            c.line(x, y0, x, y1)
        c.line(670, 230, 1008, 230)
        c.line(670, 465, 1008, 465)
        _text(c, "Considered spaces.", 748, 350, 22, "WP-Medium")
        _text(c, "A clear starting point.", 748, 315, 17, color=MUTED)
    date_y = 135
    if est.prepared_by:
        date_y = (
            _paragraph(c, f"Prepared by {est.prepared_by}", M, 157, W - 2 * M, 12, 17)
            - 5
        )
    if est.estimate_date:
        _text(
            c,
            f"{est.estimate_date:%B} {est.estimate_date.day}, {est.estimate_date.year}",
            M,
            date_y,
            12,
            color=MUTED,
        )
    _text(c, "Preliminary scope & investment", M, 83, 10, color=MUTED)


def _overview(c, est, page, factor, total, zone_count):
    _brand(c, small=True)
    _text(
        c,
        "Project Overview" + (" / continued" if page.continued else ""),
        M,
        535,
        32,
        "WP-Medium",
    )
    _text(
        c,
        f'{zone_count} project {"zone" if zone_count==1 else "zones"}',
        M,
        499,
        13,
        color=MUTED,
    )
    y = 438
    for idx, z in page.zones:
        _text(c, f"{idx:02d}", M, y, 12, color=ACCENT)
        y_after = _paragraph(c, z.label, M + 44, y, 610, 17, 23, "WP-Medium")
        _right(
            c,
            (
                (
                    "Pricing pending"
                    if _pending_only(z)
                    else money(_zone_total(z, factor))
                )
                if getattr(z, "_show_price", True)
                else ""
            ),
            W - M,
            y,
            16,
            "WP-Medium",
            MUTED if _pending_only(z) else INK,
        )
        y = y_after - 12
        _rule(c, M, y, W - 2 * M)
        y -= 25
    _text(c, "Current calculation basis", M, 111, 11, color=MUTED)
    _right(
        c,
        (
            "Pricing pending"
            if total == 0 and any(_pending(z) for _, z in page.zones)
            else money(total)
        ),
        W - M,
        101,
        29,
        "WP-Medium",
    )


def _zone(c, est, page, factor, index, count):
    z = page.zone
    paths = _photo_paths(z)
    _brand(c, small=True)
    _text(
        c,
        f"Zone {index:02d} / {count:02d}"
        + ("   ·   Continued" if page.continued else ""),
        M,
        562,
        11,
        color=MUTED,
    )
    y = 520
    for line in page.title_lines:
        _text(c, line, M, y, 30, "WP-Medium")
        y -= 36
    top = y - 4
    if page.kind == "zone-title":
        _text(
            c,
            "Project scope continues on the following slide.",
            M,
            140,
            14,
            color=MUTED,
        )
        return
    x = 536 if paths else M
    width = 560 if paths else W - 2 * M
    if paths:
        _gallery(c, paths, M, 157, 440, top - 157)
        _text(c, "Project reference", M, 140, 10, color=MUTED)
    for row in page.rows:
        baseline = top - 10
        for text, font, size, leading, color in row.lines:
            _text(c, text, x, baseline, size, font, color)
            baseline -= leading
        if row.price:
            _right(
                c,
                row.price,
                x + width,
                top - 10,
                11 if row.kind == "section" else 16,
                "WP-Medium",
                MUTED if row.kind == "section" else INK,
            )
        top -= row.height
        if row.kind == "item":
            _rule(c, x, top + 7, width)
    _rule(c, M, 118, W - 2 * M)
    _text(
        c,
        "Pricing to be confirmed" if _pending_only(z) else "Estimated zone investment",
        M,
        87,
        12,
        color=MUTED,
    )
    _right(
        c,
        "Pricing pending" if _pending_only(z) else money(_zone_total(z, factor)),
        W - M,
        82,
        25,
        "WP-Medium",
    )


def _summary(c, est, page, factor, total, pending):
    _brand(c, small=True)
    _text(
        c,
        "Investment Summary" + (" / continued" if page.continued else ""),
        M,
        535,
        32,
        "WP-Medium",
    )
    y = 477
    for _, z in page.zones:
        lines = _wrap(z.label, 730, 15, "WP-Medium")
        for line in lines:
            _text(c, line, M, y, 15, "WP-Medium")
            y -= 21
        _right(
            c,
            (
                (
                    "Pricing pending"
                    if _pending_only(z)
                    else money(_zone_total(z, factor))
                )
                if getattr(z, "_show_price", True)
                else ""
            ),
            W - M,
            y + 21,
            16,
            "WP-Medium",
            MUTED if _pending_only(z) else INK,
        )
        y -= 7
        _rule(c, M, y, W - 2 * M)
        y -= 10
    if not page.final:
        _text(
            c,
            "Investment summary continues on the following slide.",
            M,
            100,
            12,
            color=MUTED,
        )
        return
    # The established 90–115% rule is applied exactly once to the adjusted basis.
    _text(c, "Current calculation basis", M, 243, 12, color=MUTED)
    _text(
        c,
        "Pricing pending" if total == 0 and pending else money(total),
        M,
        203,
        32,
        "WP-Medium",
    )
    _text(c, "Preliminary investment range", 590, 243, 12, color=MUTED)
    _text(
        c,
        (
            "To be confirmed"
            if total == 0 and pending
            else f'{money(total*Decimal("0.90"))} – {money(total*Decimal("1.15"))}'
        ),
        590,
        203,
        29,
        "WP-Medium",
    )
    note = "This preliminary estimate is a guide, not a contract or invoice. Final pricing is subject to confirmed measurements, specifications and scope."
    if pending:
        note = (
            f'{pending} {"zone includes" if pending==1 else "zones include"} pricing to be confirmed. '
            + note
        )
    _paragraph(c, note, M, 143, W - 2 * M, 11, 17, color=MUTED)


def generate_pre_estimate(est, output_path):
    """Render any loaded Estimate, regardless of its saved Pre/Final type."""
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
    total = sum((_zone_total(z, factor) for z in zones), Decimal(0))
    pending = sum(_pending(z) for z in zones)
    client = est.client_name or est.title or "Project"
    if len(_wrap(client, 470, 48, "WP-Medium")) > 2:
        lines = _wrap(client, W - 2 * M, 32, "WP-Medium")
        pages = [
            Page("cover", title_lines=lines[n : n + 4], continued=n > 0)
            for n in range(0, len(lines), 4)
        ]
    else:
        pages = [Page("cover")]
    # Measure overview / summary rows; never force a fixed zone count into a slide.
    for kind, capacity in [("overview", 322), ("summary", 200)]:
        batch = []
        used = 0
        groups = []
        for idx, z in enumerate(zones, 1):
            name_lines = _wrap(
                z.label,
                610 if kind == "overview" else 730,
                17 if kind == "overview" else 15,
                "WP-Medium",
            )
            for part in range(0, len(name_lines), 3):
                fragment = name_lines[part : part + 3]
                entry = SimpleNamespace(
                    label="\n".join(fragment),
                    line_items=z.line_items,
                    _show_price=part == 0,
                )
                height = len(fragment) * (23 if kind == "overview" else 21) + (
                    37 if kind == "overview" else 17
                )
                if batch and used + height > capacity:
                    groups.append(batch)
                    batch = []
                    used = 0
                batch.append((idx, entry))
                used += height
        if batch or not groups:
            groups.append(batch)
        if kind == "overview":
            pages += [
                Page(kind, zones=g, continued=i > 0) for i, g in enumerate(groups)
            ]
            for z in zones:
                pages += _zone_pages(z, factor)
        else:
            pages += [
                Page(kind, zones=g, continued=i > 0, final=i == len(groups) - 1)
                for i, g in enumerate(groups)
            ]
    paths = next((_photo_paths(z) for z in zones if _photo_paths(z)), [])
    os.makedirs(os.path.dirname(str(output_path)), exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=(W, H), pageCompression=1)
    c.setTitle(f'{est.client_name or est.title or "Project"} | Pre-Estimate')
    c.setAuthor(est.prepared_by or "WallPanels")
    c.setSubject("Preliminary interior scope and investment")
    for n, page in enumerate(pages, 1):
        c.setFillColor(HexColor("#ffffff"))
        c.rect(0, 0, W, H, fill=1, stroke=0)
        if page.kind == "cover":
            _cover(c, est, paths, page)
        elif page.kind == "overview":
            _overview(c, est, page, factor, total, len(zones))
        elif page.kind.startswith("zone"):
            _zone(c, est, page, factor, zones.index(page.zone) + 1, len(zones))
        else:
            _summary(c, est, page, factor, total, pending)
        _footer(c, est, n, len(pages))
        c.showPage()
    c.save()
    return str(output_path)
