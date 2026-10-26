import os
import uuid
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable, PageBreak, KeepInFrame
)
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from PIL import Image as PILImage

BLACK = colors.HexColor('#111111')
GRAY = colors.HexColor('#888888')
LIGHT_GRAY = colors.HexColor('#f0f0f0')
MID_GRAY = colors.HexColor('#dddddd')

# Landscape letter usable area
PAGE_W = 10.2 * inch   # 11in - 0.8in margins
PAGE_H = 7.15 * inch   # 8.5in - margins, with safety margin for frame + brand padding
GAP_COL = 0.3 * inch    # visual gap between photo and text
COL_W = PAGE_W / 3      # left column = 1/3 of page width
RIGHT_W = PAGE_W - COL_W - GAP_COL  # right column = remaining 2/3 minus gap
BRAND_H = 0.55 * inch
FOOTER_H = 40  # unified height (pt) for the bottom brand bar and the zone total bar


def fmt_money(value, prefix="$") -> str:
    try:
        return f"{prefix}{float(value):,.0f}"
    except Exception:
        return f"{prefix}0"


def fmt_range(value, prefix="$") -> str:
    """Pre-estimate range: -10% to +15% of the calculated total."""
    try:
        v = float(value)
        low = v * 0.90
        high = v * 1.15
        return f"{prefix}{low:,.0f} \u2013 {prefix}{high:,.0f}"
    except Exception:
        return f"{prefix}0"


def _cover_image(path, box_w_pt, box_h_pt, dpi=150, cache_dir=None):
    """Return an Image flowable that fills box_w_pt x box_h_pt completely
    ("object-fit: cover"), cropping the source image as needed so there are
    no empty letterbox bars regardless of the source aspect ratio (portrait,
    landscape, or square all fill the box edge-to-edge).

    The processed (resized + cropped) image is cached on disk next to the
    original so repeated PDF generations don't redo the work.
    """
    try:
        box_w_px = max(1, int(round(box_w_pt / 72.0 * dpi)))
        box_h_px = max(1, int(round(box_h_pt / 72.0 * dpi)))

        cache_dir = cache_dir or os.path.dirname(path)
        base, _ext = os.path.splitext(os.path.basename(path))
        cache_path = os.path.join(cache_dir, f"{base}_cover_{box_w_px}x{box_h_px}.jpg")

        if not os.path.exists(cache_path) or os.path.getmtime(cache_path) < os.path.getmtime(path):
            with PILImage.open(path) as im:
                # Flatten transparency onto white (JPEG has no alpha channel)
                if im.mode in ("RGBA", "LA", "P"):
                    bg = PILImage.new("RGB", im.size, (255, 255, 255))
                    rgba = im.convert("RGBA")
                    bg.paste(rgba, mask=rgba.split()[-1])
                    im = bg
                else:
                    im = im.convert("RGB")

                img_w, img_h = im.size
                if img_w <= 0 or img_h <= 0:
                    return Spacer(box_w_pt, box_h_pt)

                # Scale so the image FULLY COVERS the box (may overflow one dimension)
                scale = max(box_w_px / img_w, box_h_px / img_h)
                new_w = max(1, int(round(img_w * scale)))
                new_h = max(1, int(round(img_h * scale)))
                im = im.resize((new_w, new_h), PILImage.LANCZOS)

                # Center-crop to exactly box_w_px x box_h_px
                left = max(0, (new_w - box_w_px) // 2)
                top = max(0, (new_h - box_h_px) // 2)
                im = im.crop((left, top, left + box_w_px, top + box_h_px))

                im.save(cache_path, "JPEG", quality=85)

        img_flowable = Image(cache_path, width=box_w_pt, height=box_h_pt)
        img_flowable._restrictSize(box_w_pt, box_h_pt)
        return img_flowable

    except Exception:
        return Spacer(box_w_pt, box_h_pt)


def _fit_image(path, box_w, box_h):
    """Return a flowable of exactly box_w x box_h with the image centered inside,
    scaled to fit while preserving its original aspect ratio."""
    try:
        with PILImage.open(path) as im:
            img_w, img_h = im.size
    except Exception:
        return Spacer(box_w, box_h)

    if img_w <= 0 or img_h <= 0:
        return Spacer(box_w, box_h)

    scale = min(box_w / img_w, box_h / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale

    try:
        img_flowable = Image(path, width=draw_w, height=draw_h)
        # Safety net: some images (unusual DPI metadata, rounding) can report
        # a drawn size slightly larger than requested, which causes ReportLab
        # to silently grow the containing Table beyond the page frame and
        # raise LayoutError. _restrictSize hard-clamps to box_w x box_h.
        img_flowable._restrictSize(box_w, box_h)
    except Exception:
        return Spacer(box_w, box_h)

    container = Table([[img_flowable]], colWidths=[box_w], rowHeights=[box_h])
    container.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return container


def generate_pdf(estimate, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    pdf_filename = f"{uuid.uuid4()}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=landscape(letter),
        rightMargin=0.4 * inch,
        leftMargin=0.4 * inch,
        topMargin=0.4 * inch,
        bottomMargin=0.4 * inch,
    )

    story = []
    zones = sorted(estimate.zones, key=lambda z: z.sort_order)
    is_pre = estimate.type == "pre"
    money_prefix = "~$" if is_pre else "$"

    # Markup multiplier (hidden from client — silently scales all prices in PDF)
    markup_pct = float(estimate.markup_pct or 0)
    markup_factor = 1 + markup_pct / 100  # e.g. 15% → 1.15

    # Discount pct (visible to client — applied to totals only)
    discount_pct = float(estimate.discount_pct or 0)

    # Cover page — client/project info, shown only once
    story.extend(_cover_page(estimate, money_prefix, is_pre))
    story.append(PageBreak())

    zones_with_items = [z for z in zones if z.line_items]
    for i, zone in enumerate(zones_with_items):
        story.extend(_zone_page(estimate, zone, money_prefix, is_pre, markup_factor))
        story.append(PageBreak())

    # Summary page
    story.extend(_summary_page(estimate, zones_with_items, money_prefix, is_pre, markup_factor, discount_pct))

    doc.build(story)
    return pdf_path


def _cover_page(estimate, money_prefix, is_pre):
    content = []

    brand_style = ParagraphStyle('brand', fontSize=13, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=2)
    brand_sub_style = ParagraphStyle('brandsub', fontSize=8, textColor=colors.HexColor('#aaaaaa'), alignment=TA_CENTER)
    label_style = ParagraphStyle('label', fontSize=7, textColor=GRAY)
    val_style = ParagraphStyle('val', fontSize=11, textColor=BLACK, fontName='Helvetica-Bold')
    title_style = ParagraphStyle('title', fontSize=28, textColor=BLACK, fontName='Helvetica-Bold', spaceAfter=8, leading=34)
    badge_style = ParagraphStyle('badge', fontSize=7, textColor=GRAY)

    content.append(Spacer(1, 0.6 * inch))

    # Brand block
    brand_table = Table([
        [Paragraph("WALLPANELS.COM", brand_style)],
        [Paragraph("By VERONA HOME", brand_sub_style)],
    ], colWidths=[PAGE_W])
    brand_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 16),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    content.append(brand_table)
    content.append(Spacer(1, 0.5 * inch))

    content.append(Paragraph("PRE-ESTIMATE" if is_pre else "COST ESTIMATE", badge_style))
    content.append(Paragraph(estimate.title or "Project Estimate", title_style))

    if estimate.description:
        content.append(Paragraph(estimate.description, ParagraphStyle('desc', fontSize=10, textColor=GRAY, spaceAfter=20, leading=15)))
    else:
        content.append(Spacer(1, 14))

    date_str = estimate.estimate_date.strftime('%m/%d/%y') if estimate.estimate_date else '-'
    meta_data = [
        [Paragraph("ESTIMATE TITLE", label_style), Paragraph("CLIENT", label_style),
         Paragraph("PROJECT", label_style), Paragraph("PREPARED BY", label_style), Paragraph("DATE", label_style)],
        [Paragraph(estimate.title or '-', val_style), Paragraph(estimate.client_name or '-', val_style),
         Paragraph(estimate.project_name or '-', val_style), Paragraph(estimate.prepared_by or '-', val_style),
         Paragraph(date_str, val_style)],
    ]
    meta_table = Table(meta_data, colWidths=[PAGE_W / 5] * 5)
    meta_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, MID_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    content.append(meta_table)

    if estimate.notes:
        content.append(Spacer(1, 16))
        content.append(Paragraph(f"Notes: {estimate.notes}", ParagraphStyle('notes', fontSize=8.5, textColor=GRAY)))

    if is_pre:
        content.append(Spacer(1, 30))
        content.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY))
        content.append(Paragraph(
            "This is a preliminary estimate. Final pricing subject to site visit and detailed scope review.",
            ParagraphStyle('footer', fontSize=7.5, textColor=GRAY, alignment=TA_CENTER, spaceBefore=8)
        ))

    return content


def _zone_page(estimate, zone, money_prefix, is_pre, markup_factor=1.0):
    content = []

    label_style = ParagraphStyle('label', fontSize=6, textColor=GRAY, spaceAfter=1)
    val_style = ParagraphStyle('val', fontSize=8, textColor=BLACK, fontName='Helvetica-Bold')
    title_style = ParagraphStyle('title', fontSize=16, textColor=BLACK, fontName='Helvetica-Bold', spaceAfter=10, leading=20)
    section_style = ParagraphStyle('section', fontSize=6.5, textColor=GRAY, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=3)
    item_name_style = ParagraphStyle('iname', fontSize=8, textColor=BLACK, fontName='Helvetica-Bold')
    item_desc_style = ParagraphStyle('idesc', fontSize=7, textColor=GRAY)
    price_style = ParagraphStyle('price', fontSize=8.5, textColor=BLACK, fontName='Helvetica-Bold', alignment=TA_RIGHT)
    brand_style = ParagraphStyle('brand', fontSize=11, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=2)
    brand_sub_style = ParagraphStyle('brandsub', fontSize=7, textColor=colors.HexColor('#aaaaaa'), alignment=TA_CENTER)
    badge_style = ParagraphStyle('badge', fontSize=6, textColor=GRAY)

    # ===== RIGHT column (2/3 width) — content independent of image size =====
    right_content = []

    right_content.append(Paragraph("PRE-ESTIMATE" if is_pre else "COST ESTIMATE", badge_style))

    title_text = zone.label or zone.room_name or zone.wall_name or "Zone"
    if zone.room_name and zone.wall_name and zone.room_name != zone.wall_name:
        title_text = f"{zone.room_name} - {zone.wall_name}"
    right_content.append(Paragraph(title_text, title_style))

    if zone.notes:
        right_content.append(Paragraph(zone.notes, ParagraphStyle('desc', fontSize=7.5, textColor=GRAY, spaceAfter=8)))
    else:
        right_content.append(Spacer(1, 6))

    # Dimensions row only (no client/project info on zone pages)
    dim_data = [[
        Paragraph("WIDTH", label_style), Paragraph("HEIGHT", label_style),
        Paragraph("SQUARE FOOTAGE", label_style), Paragraph("LINEAR FOOTAGE", label_style),
    ], [
        Paragraph(f"{float(zone.wall_width_ft):.1f} ft" if zone.wall_width_ft else "-", val_style),
        Paragraph(f"{float(zone.wall_height_ft):.1f} ft" if zone.wall_height_ft else "-", val_style),
        Paragraph(f"{float(zone.square_footage):.0f} SF" if zone.square_footage else "-", val_style),
        Paragraph(f"{float(zone.linear_footage):.1f} LF" if zone.linear_footage else "-", val_style),
    ]]
    dim_table = Table(dim_data, colWidths=[RIGHT_W / 4] * 4)
    dim_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, MID_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    right_content.append(dim_table)
    right_content.append(Spacer(1, 8))

    # Line items grouped by section, sorted by priority:
    # 1. Wall Panels  2. Cabinetry  3. Other  4. Services
    def section_priority(sec: str) -> int:
        s = sec.lower()
        if 'wall panel' in s or 'wall panels' in s: return 0
        if 'cabinet' in s or 'cabinetry' in s: return 1
        if 'service' in s: return 3
        return 2  # Lighting, Mirrors, Finishes, Accessories, etc.

    sections = {}
    for item in sorted(zone.line_items, key=lambda x: x.sort_order):
        sec = item.section or "General"
        sections.setdefault(sec, []).append(item)

    # Apply priority sort to section order
    sections = dict(sorted(sections.items(), key=lambda kv: section_priority(kv[0])))

    item_col_w = RIGHT_W - 0.2 * inch - 0.8 * inch

    row_num = 1
    for section_name, items in sections.items():
        right_content.append(Paragraph(section_name.upper(), section_style))
        right_content.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY))

        section_total = 0
        for item in items:
            desc_parts = [Paragraph(item.name, item_name_style)]
            if item.description:
                desc_parts.append(Paragraph(item.description, item_desc_style))

            # Build qty × unit_price / unit line — only when all values present
            qty     = item.quantity
            uprice  = item.unit_price
            unit    = item.unit if item.unit and str(item.unit).lower() not in ('none', '') else None
            total   = item.total_price

            is_tbd      = getattr(item, 'is_tbd', False)
            is_zero_svc = (not is_tbd) and (not total or float(total) == 0) and (not uprice or float(uprice) == 0)
            is_service  = (item.section or '').lower() == 'services'

            if is_tbd:
                # TBD item: show "TBD" bold + "To be discussed" small gray
                tbd_style  = ParagraphStyle('tbd', fontSize=11, textColor=BLACK, fontName='Helvetica-Bold', alignment=TA_RIGHT)
                tbds_style = ParagraphStyle('tbds', fontSize=7.5, textColor=GRAY, alignment=TA_RIGHT)
                total_cell = [Paragraph("TBD", tbd_style), Paragraph("To be discussed", tbds_style)]
                # Don't add to section_total
            elif is_zero_svc and is_service:
                # Service with no price → "Included in quote" light gray
                inc_style = ParagraphStyle('inc', fontSize=8.5, textColor=GRAY, fontName='Helvetica-Oblique', alignment=TA_RIGHT)
                total_cell = [Paragraph("Included in quote", inc_style)]
            else:
                if item.calc_type in ('sf', 'lf') and qty and uprice and unit:
                    display_uprice = float(uprice) * markup_factor
                    desc_parts.append(Paragraph(
                        f"{float(qty):.0f} {unit} \u00d7 ${display_uprice:,.0f} / {unit}",
                        item_desc_style))
                elif item.calc_type == 'fixed' and qty and uprice and markup_factor != 1.0:
                    display_uprice = float(uprice) * markup_factor
                    qty_int = int(float(qty)) if float(qty) == int(float(qty)) else float(qty)
                    unit_label = unit or 'ea'
                    desc_parts.append(Paragraph(
                        f"${display_uprice:,.0f} / {unit_label} \u00d7 {qty_int}",
                        item_desc_style))

                display_total = float(total) * markup_factor if total else None
                show_dash = (
                    display_total is None or
                    display_total == 0 and (not uprice or float(uprice) == 0)
                )
                total_str  = "-" if show_dash else fmt_money(display_total, money_prefix)
                total_cell = [Paragraph(total_str, price_style)]
                section_total += float(total or 0) * markup_factor

            row_table = Table([[
                Paragraph(str(row_num), ParagraphStyle('num', fontSize=7, textColor=GRAY)),
                desc_parts,
                total_cell,
            ]], colWidths=[0.2 * inch, item_col_w, 0.8 * inch])
            row_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LINEBELOW', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            right_content.append(row_table)
            row_num += 1

        sub_table = Table([[
            '', Paragraph(f"{section_name} subtotal", ParagraphStyle('sub', fontSize=7, textColor=GRAY, fontName='Helvetica-Oblique')),
            Paragraph("-" if section_total == 0 else fmt_money(section_total, money_prefix), ParagraphStyle('subp', fontSize=7.5, textColor=GRAY, alignment=TA_RIGHT)),
        ]], colWidths=[0.2 * inch, item_col_w, 0.8 * inch])
        sub_table.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, MID_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        right_content.append(sub_table)

    # Zone total is rendered in the unified footer bar below (spans full page
    # width), not here — so it stays at a fixed vertical position regardless
    # of how many line items this zone has.
    has_tbd = any(getattr(item, 'is_tbd', False) for item in zone.line_items)
    zone_sub = float(zone.subtotal) * markup_factor if zone.subtotal else 0
    if zone_sub == 0 and not has_tbd:
        zone_total_str = "-"
    elif is_pre:
        zone_total_str = fmt_range(zone_sub)
    else:
        zone_total_str = fmt_money(zone_sub, money_prefix)
    if has_tbd:
        zone_total_str += "  + TBD Items"
    total_value_fontsize = 12 if is_pre else 14

    # Both columns of main_table (photo area / line items) share the same
    # height: the page frame minus the unified footer bar below them.
    CONTENT_H = PAGE_H - FOOTER_H
    PHOTO_AREA_H = CONTENT_H
    GAP = 0.06 * inch

    existing_images = sorted([img for img in zone.images if os.path.exists(img.file_path)], key=lambda x: x.slot)
    left_content = []

    if len(existing_images) == 0:
        no_photo_style = ParagraphStyle('nophoto', fontSize=9, textColor=colors.HexColor('#bbbbbb'), alignment=TA_CENTER, fontName='Helvetica')
        placeholder = Table([[Paragraph("No photo for this zone", no_photo_style)]], colWidths=[COL_W], rowHeights=[PHOTO_AREA_H])
        placeholder.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f3')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e8e4e0')),
        ]))
        left_content.append(placeholder)
    elif len(existing_images) == 1:
        left_content.append(_cover_image(existing_images[0].file_path, COL_W, PHOTO_AREA_H))
    elif len(existing_images) == 2:
        h = (PHOTO_AREA_H - GAP) / 2
        for idx, img in enumerate(existing_images):
            left_content.append(_cover_image(img.file_path, COL_W, h))
            if idx == 0:
                left_content.append(Spacer(1, GAP))
    else:
        # 3 or 4 images -> 2x2 grid. Each cell reserves GAP of padding on its
        # right/bottom edge (via TableStyle below); the image itself is sized
        # to the padded content area (cell - GAP) so it fills that area
        # edge-to-edge with no empty bars, for any source aspect ratio.
        cell_w = (COL_W - GAP) / 2
        cell_h = (PHOTO_AREA_H - GAP) / 2
        img_w = cell_w - GAP
        img_h = cell_h - GAP
        imgs = existing_images[:4]
        while len(imgs) < 4:
            imgs.append(None)
        cells = [_cover_image(img.file_path, img_w, img_h) if img else Spacer(img_w, img_h) for img in imgs]
        grid = Table([[cells[0], cells[1]], [cells[2], cells[3]]], colWidths=[cell_w, cell_w], rowHeights=[cell_h, cell_h])
        grid.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), GAP),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), GAP),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        left_content.append(grid)

    # Wrap the right column in KeepInFrame(mode='shrink') as a safety net:
    # if a zone has many line items / long descriptions and the natural
    # height of right_content would exceed the available content height,
    # KeepInFrame scales the whole block down to fit instead of raising
    # LayoutError. maxHeight matches the left column's photo area height so
    # both columns end at the same Y, with the footer immediately below.
    right_block = KeepInFrame(
        maxWidth=RIGHT_W,
        maxHeight=CONTENT_H,
        content=right_content,
        mode='shrink',
        hAlign='LEFT',
    )

    main_table = Table([[left_content, '', right_block]], colWidths=[COL_W, GAP_COL, RIGHT_W])
    main_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (0, 0), 'TOP'),
        ('VALIGN', (2, 0), (2, 0), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    content.append(main_table)

    # ===== Unified footer bar — spans the FULL page width seamlessly =====
    # Sits directly below main_table (whose two columns are both CONTENT_H
    # tall), so this bar always lands at the same vertical position
    # (PAGE_H - FOOTER_H from the top) on every zone page, regardless of
    # photo count or number of line items.
    footer_data = [[
        [Paragraph("WALLPANELS.COM", brand_style), Paragraph("By VERONA HOME", brand_sub_style)],
        Paragraph(f"TOTAL - {title_text.upper()}", ParagraphStyle('tl', fontSize=7.5, textColor=colors.white, fontName='Helvetica-Bold')),
        Paragraph(zone_total_str, ParagraphStyle('tv', fontSize=total_value_fontsize, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
    ]]
    total_col_w = 2.4 * inch if is_pre else 1.2 * inch
    footer_table = Table(footer_data, colWidths=[COL_W + GAP_COL, RIGHT_W - total_col_w, total_col_w], rowHeights=[FOOTER_H])
    footer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLACK),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ('LEFTPADDING', (1, 0), (1, 0), 14),
        ('RIGHTPADDING', (1, 0), (1, 0), 10),
        ('LEFTPADDING', (2, 0), (2, 0), 10),
        ('RIGHTPADDING', (2, 0), (2, 0), 14),
    ]))
    content.append(footer_table)

    return content


def _summary_page(estimate, zones, money_prefix, is_pre, markup_factor=1.0, discount_pct=0.0):
    content = []

    title_style = ParagraphStyle('title', fontSize=20, textColor=BLACK, fontName='Helvetica-Bold', spaceAfter=4)
    zone_name_style = ParagraphStyle('zname', fontSize=10, textColor=BLACK, fontName='Helvetica-Bold')
    zone_price_style = ParagraphStyle('zprice', fontSize=10 if is_pre else 11, textColor=BLACK, fontName='Helvetica-Bold', alignment=TA_RIGHT)

    header_data = [[
        Paragraph("WALLPANELS.COM  \u00b7  By VERONA HOME", ParagraphStyle('brand', fontSize=9, fontName='Helvetica-Bold', textColor=colors.white)),
        Paragraph("PROJECT SUMMARY" if not is_pre else "PRE-ESTIMATE SUMMARY", ParagraphStyle('badge', fontSize=8, textColor=colors.white, alignment=TA_RIGHT)),
    ]]
    header_table = Table(header_data, colWidths=[PAGE_W / 2] * 2)
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLACK),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
    ]))
    content.append(header_table)
    content.append(Spacer(1, 16))

    title = estimate.title or "Project Estimate"
    content.append(Paragraph(title, title_style))
    content.append(Spacer(1, 8))

    content.append(Paragraph("PROJECT BREAKDOWN", ParagraphStyle('section', fontSize=8, textColor=GRAY, fontName='Helvetica-Bold', spaceAfter=4)))
    content.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY))

    grand_total = 0
    for zone in zones:
        title_text = zone.label or zone.room_name or zone.wall_name or "Zone"
        if zone.room_name and zone.wall_name and zone.room_name != zone.wall_name:
            title_text = f"{zone.room_name} - {zone.wall_name}"

        dims = []
        if zone.square_footage:
            dims.append(f"{float(zone.square_footage):.0f} SF")
        if zone.linear_footage:
            dims.append(f"{float(zone.linear_footage):.1f} LF")
        dims_str = "  \u00b7  ".join(dims)

        zone_sub_marked = float(zone.subtotal) * markup_factor
        zone_has_tbd = any(getattr(item, 'is_tbd', False) for item in zone.line_items)
        zone_total_str = fmt_range(zone_sub_marked) if is_pre else fmt_money(zone_sub_marked, money_prefix)
        if zone_has_tbd:
            zone_total_str += "  + TBD Items"
        row_price_col_w = 2.4 * inch if is_pre else 1.8 * inch
        row = Table([[
            [Paragraph(title_text, zone_name_style), Paragraph(dims_str, ParagraphStyle('dims', fontSize=8, textColor=GRAY))],
            Paragraph(zone_total_str, zone_price_style),
        ]], colWidths=[PAGE_W - row_price_col_w, row_price_col_w])
        row.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        content.append(row)
        grand_total += zone_sub_marked

    content.append(Spacer(1, 16))

    # Discount line — visible to client
    if discount_pct and discount_pct > 0:
        discount_amount = grand_total * discount_pct / 100
        discount_str = f"\u2212{fmt_money(discount_amount, '$')}"  # always show exact amount
        discount_pct_style = ParagraphStyle('discpct', fontSize=9, textColor=GRAY)
        discount_amt_style = ParagraphStyle('discamt', fontSize=9, textColor=GRAY, alignment=TA_RIGHT)
        disc_price_col_w = 1.8 * inch
        disc_row = Table([[
            Paragraph(f"Discount ({discount_pct:.0f}%)", discount_pct_style),
            Paragraph(discount_str, discount_amt_style),
        ]], colWidths=[PAGE_W - disc_price_col_w, disc_price_col_w])
        disc_row.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, MID_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        content.append(disc_row)
        grand_total -= discount_amount

    any_tbd = any(
        getattr(item, 'is_tbd', False)
        for zone in zones
        for item in zone.line_items
    )

    total_label = "ESTIMATED PROJECT TOTAL" if is_pre else "GRAND TOTAL"
    grand_total_str = fmt_range(grand_total) if is_pre else fmt_money(grand_total, money_prefix)
    if any_tbd:
        grand_total_str += "  + TBD Items"
    grand_fontsize = 15 if is_pre else 18
    total_data = [[
        Paragraph(total_label, ParagraphStyle('tl', fontSize=10, textColor=colors.white, fontName='Helvetica-Bold')),
        Paragraph(grand_total_str, ParagraphStyle('tv', fontSize=grand_fontsize, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
    ]]
    total_col_w = 3.0 * inch if is_pre else 1.8 * inch
    total_table = Table(total_data, colWidths=[PAGE_W - total_col_w, total_col_w])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    content.append(total_table)

    if estimate.notes:
        content.append(Spacer(1, 12))
        content.append(Paragraph(f"Notes: {estimate.notes}", ParagraphStyle('notes', fontSize=8, textColor=GRAY)))

    if is_pre:
        content.append(Spacer(1, 16))
        content.append(HRFlowable(width="100%", thickness=0.5, color=MID_GRAY))
        content.append(Paragraph(
            "This is a preliminary estimate. Final pricing subject to site visit and detailed scope review.",
            ParagraphStyle('footer', fontSize=7, textColor=GRAY, alignment=TA_CENTER, spaceBefore=6)
        ))

    return content