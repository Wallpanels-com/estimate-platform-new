"""
Project Passport export (XLSX).

Renders an estimate into the WallPanels "Project Passport" spreadsheet.

To reproduce the source template pixel-for-pixel (colours, borders, fonts,
number formats, the whole internal cost-tracking block and its formulas), we
open the bundled template file itself and edit it in place:

  * BRIEF INFORMATION values are filled from the fields we have; the rest of
    the labelled rows are left empty.
  * The DETAILED ESTIMATE left table (cols A–I, rows 19+) is cleared and
    rebuilt dynamically from the estimate's zones and line items, reusing the
    exact per-column styles captured from the template's own reference rows
    (zone header row 19, item row 20, zone-total row 58, grand-total row 108).
  * The INTERNAL COST TRACKING block (cols J–Q) and the profitability summary
    are left untouched, so they stay identical to the template. Their two
    references into the left table (grand total) are repointed to wherever the
    rebuilt grand-total row lands.
"""
import copy
import os
import re
from decimal import Decimal

from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Border, Font, Alignment
from openpyxl.formatting.rule import CellIsRule

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "project_passport_template.xlsx")

# Left client table columns (1-based)
C_ZONE, C_DESIGN, C_SPEC, C_CODE, C_UNIT, C_PRICE, C_QTY, C_TOTAL = 2, 3, 4, 5, 6, 7, 8, 9

# Template reference rows for the left table
R_HEADER = 18      # column headers
R_ZONE   = 19      # zone header row
R_ITEM   = 20      # line item row
R_ZTOTAL = 58      # "TOTAL per Zone" row
R_GTOTAL = 108     # "TOTAL Estimate" row
R_CLEAR_TO = 110   # clear left cells down to here before rebuilding

# Profitability summary (Planned / Fact / Variance) — in the template it sits at
# the bottom (rows 106-110). We relocate it to the top of the sheet, to the
# right of the BRIEF INFORMATION block.
R_PROFIT_SRC_TOP = 106   # header row of the block in the template
R_PROFIT_ROWS = 5        # header + 4 data rows
C_PROFIT_FIRST, C_PROFIT_LAST = 10, 17   # cols J..Q
R_PROFIT_DEST_TOP = 4    # where the block's header lands after the move

_BLANK_FILL = PatternFill(fill_type=None)
_NO_BORDER = Border()


def _num(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


def _style_of(cell):
    return dict(font=copy.copy(cell.font), fill=copy.copy(cell.fill),
                border=copy.copy(cell.border), alignment=copy.copy(cell.alignment),
                numfmt=cell.number_format)


def _row_styles(ws, row):
    """Capture per-column styles for the left table (cols B–I) of a reference row."""
    return {c: _style_of(ws.cell(row=row, column=c)) for c in range(C_ZONE, C_TOTAL + 1)}


def _apply(cell, style, value=None):
    cell.font = copy.copy(style["font"])
    cell.fill = copy.copy(style["fill"])
    cell.border = copy.copy(style["border"])
    cell.alignment = copy.copy(style["alignment"])
    cell.number_format = style["numfmt"]
    if value is not None:
        cell.value = value


def _zone_label(idx, zone):
    label = getattr(zone, "label", None) or "Zone"
    sf = _num(getattr(zone, "square_footage", None))
    lf = _num(getattr(zone, "linear_footage", None))
    dims = []
    if sf:
        dims.append(f"{sf:g} SF")
    if lf:
        dims.append(f"{lf:g} LF")
    suffix = f" ({', '.join(dims)})" if dims else ""
    return f"Zone {idx} - {label}{suffix}"


def _fill_brief(ws, est):
    zones = list(getattr(est, "zones", []) or [])
    values = {
        2:  getattr(est, "project_name", None),   # Project ID
        3:  getattr(est, "client_name", None),    # Client Name
        9:  len(zones) if zones else None,         # Number of Zones
        12: getattr(est, "notes", None),           # Manager Notes
        13: getattr(est, "prepared_by", None),     # Project Manager
    }
    for row, value in values.items():
        if value not in (None, ""):
            ws.cell(row=row, column=C_DESIGN).value = value  # merged C:I, anchor at C


def _clear_left(ws):
    for r in range(R_ZONE, R_CLEAR_TO + 1):
        for c in range(1, C_TOTAL + 1):
            cell = ws.cell(row=r, column=c)
            cell.value = None
            cell.fill = _BLANK_FILL
            cell.border = _NO_BORDER
            cell.font = Font()
            cell.alignment = Alignment()
            cell.number_format = "General"


def _iter_zone_items(est):
    """Yield (label, items) blocks: one per zone, plus a trailing block for any
    zone-less line items."""
    zones = list(getattr(est, "zones", []) or [])
    for idx, zone in enumerate(zones, start=1):
        items = sorted(list(getattr(zone, "line_items", []) or []),
                       key=lambda x: getattr(x, "sort_order", 0))
        yield _zone_label(idx, zone), items
    direct = [li for li in (getattr(est, "line_items", []) or []) if getattr(li, "zone_id", None) is None]
    if direct:
        direct.sort(key=lambda x: getattr(x, "sort_order", 0))
        n = len(zones)
        label = f"Zone {n + 1} - Other" if n else "Other items"
        yield label, direct


def _rebuild_left(ws, est, styles):
    ZONE, ITEM, ZTOT, GTOT = styles
    row = R_ZONE
    zone_total_rows = []

    for label, items in _iter_zone_items(est):
        # Zone header
        for c in range(C_ZONE, C_TOTAL + 1):
            _apply(ws.cell(row=row, column=c), ZONE[c])
        ws.cell(row=row, column=C_ZONE).value = label
        first_item = row + 1
        row += 1

        for li in items:
            _apply(ws.cell(row=row, column=C_ZONE), ITEM[C_ZONE])
            _apply(ws.cell(row=row, column=C_DESIGN), ITEM[C_DESIGN], getattr(li, "name", None))
            _apply(ws.cell(row=row, column=C_SPEC), ITEM[C_SPEC], getattr(li, "description", None))
            _apply(ws.cell(row=row, column=C_CODE), ITEM[C_CODE])
            _apply(ws.cell(row=row, column=C_UNIT), ITEM[C_UNIT], getattr(li, "unit", None))
            _apply(ws.cell(row=row, column=C_PRICE), ITEM[C_PRICE], _num(getattr(li, "unit_price", None)))
            _apply(ws.cell(row=row, column=C_QTY), ITEM[C_QTY], _num(getattr(li, "quantity", None)))
            _apply(ws.cell(row=row, column=C_TOTAL), ITEM[C_TOTAL], "TBD" if getattr(li, "is_tbd", False) else _num(getattr(li, "total_price", None)))
            row += 1

        last_item = row - 1
        # Per-zone total
        for c in range(C_ZONE, C_TOTAL + 1):
            _apply(ws.cell(row=row, column=c), ZTOT[c])
        ws.cell(row=row, column=C_ZONE).value = "TOTAL per Zone"
        ws.cell(row=row, column=C_TOTAL).value = (
            f"=SUM(I{first_item}:I{last_item})" if last_item >= first_item else 0
        )
        zone_total_rows.append(row)
        row += 1

    # Grand total
    base = "+".join(f"I{r}" for r in zone_total_rows) or "0"
    adjustment_rows = []
    markup = Decimal(str(getattr(est, "markup_pct", 0) or 0))
    discount = Decimal(str(getattr(est, "discount_pct", 0) or 0))
    factor = f"(1+{markup}/100)*(1-{discount}/100)"
    adjustments = []
    if markup:
        adjustments.append((f"Markup ({markup:g}%)", f"=ROUND(({base})*{markup}/100,2)"))
    if discount:
        adjustments.append((f"Discount ({discount:g}%)", f"=ROUND(({base})*{factor},2)-ROUND(({base})*(1+{markup}/100),2)"))
    if getattr(est, "manual_override", False):
        final = Decimal(str(est.final_total))
        adjustments.append(("Manual project adjustment", f"=ROUND({final}*{factor},2)-ROUND(({base})*{factor},2)"))
    for label, formula in adjustments:
        for c in range(C_ZONE, C_TOTAL + 1):
            _apply(ws.cell(row=row, column=c), ZTOT[c])
        ws.cell(row=row, column=C_PRICE).value = label
        ws.cell(row=row, column=C_TOTAL).value = formula
        adjustment_rows.append(row)
        row += 1
    for c in range(C_ZONE, C_TOTAL + 1):
        _apply(ws.cell(row=row, column=c), GTOT[c])
    ws.cell(row=row, column=C_PRICE).value = "TOTAL Estimate"
    if zone_total_rows:
        ws.cell(row=row, column=C_TOTAL).value = "=" + "+".join(f"I{r}" for r in zone_total_rows + adjustment_rows)
    else:
        ws.cell(row=row, column=C_TOTAL).value = _num(getattr(est, "final_total", 0)) or 0
    return row  # grand-total row


def _relocate_profitability(ws):
    """Move the profitability summary block from the template's bottom rows up to
    the top of the sheet (beside BRIEF INFORMATION). Intra-block row references
    are shifted to the new position; references to the grand total and to the
    internal cost totals (O58/P58) are left as-is."""
    delta = R_PROFIT_DEST_TOP - R_PROFIT_SRC_TOP
    if delta == 0:
        return
    src_rows = range(R_PROFIT_SRC_TOP, R_PROFIT_SRC_TOP + R_PROFIT_ROWS)
    lo, hi = R_PROFIT_SRC_TOP, R_PROFIT_SRC_TOP + R_PROFIT_ROWS - 1
    ref_pat = re.compile(rf'(?<![A-Za-z$])([M-P])({lo}|{lo+1}|{lo+2}|{lo+3}|{hi})(?![0-9])')

    def _shift(formula):
        return ref_pat.sub(lambda m: m.group(1) + str(int(m.group(2)) + delta), formula)

    for rs in src_rows:  # dest is above source, no overlap → ascending is safe
        rd = rs + delta
        # Copy only the block's actual content (cols L–P). The decorative empty
        # grey cells in J/K are intentionally left out so they stay blank.
        for c in range(12, 17):  # L..P
            s = ws.cell(row=rs, column=c)
            d = ws.cell(row=rd, column=c)
            val = s.value
            if isinstance(val, str) and val.startswith("="):
                val = _shift(val)
            d.value = val
            if s.has_style:
                d.font = copy.copy(s.font)
                d.fill = copy.copy(s.fill)
                d.border = copy.copy(s.border)
                d.alignment = copy.copy(s.alignment)
                d.number_format = s.number_format
        # Clear the whole source strip (J..Q), including the grey J/K tail.
        for c in range(C_PROFIT_FIRST, C_PROFIT_LAST + 1):
            s = ws.cell(row=rs, column=c)
            s.value = None
            s.fill = _BLANK_FILL
            s.border = _NO_BORDER
            s.font = Font()
            s.alignment = Alignment()
            s.number_format = "General"


def _highlight_profitability(ws):
    """Conditional formatting on the Profitability % row: < 50% red, >= 50% green."""
    pct_row = R_PROFIT_DEST_TOP + R_PROFIT_ROWS - 1  # last row of the block
    rng = f"M{pct_row}:N{pct_row}"
    red_fill = PatternFill(start_color="FFFFC7CE", end_color="FFFFC7CE", fill_type="solid")
    green_fill = PatternFill(start_color="FFC6EFCE", end_color="FFC6EFCE", fill_type="solid")
    red_font = Font(bold=True, color="FF9C0006")
    green_font = Font(bold=True, color="FF006100")
    ws.conditional_formatting.add(
        rng, CellIsRule(operator="lessThan", formula=["0.5"], fill=red_fill, font=red_font))
    ws.conditional_formatting.add(
        rng, CellIsRule(operator="greaterThanOrEqual", formula=["0.5"], fill=green_fill, font=green_font))


def generate_passport(est, output_path):
    wb = load_workbook(TEMPLATE_PATH)
    ws = wb.active

    # Capture the template's left-table styles before we clear anything.
    styles = (_row_styles(ws, R_ZONE), _row_styles(ws, R_ITEM),
              _row_styles(ws, R_ZTOTAL), _row_styles(ws, R_GTOTAL))

    _fill_brief(ws, est)
    _clear_left(ws)
    grand_row = _rebuild_left(ws, est, styles)

    # The internal block references the left grand total by its original cell
    # (I108) in several formulas (J58, M107, M110, N110…). Repoint every such
    # reference to wherever the rebuilt grand-total row landed.
    if grand_row != R_GTOTAL:
        pat = re.compile(r'(?<![A-Za-z0-9$])I108(?![0-9])')
        for col in ws.iter_cols():
            for cell in col:
                v = cell.value
                if isinstance(v, str) and v.startswith("=") and "I108" in v:
                    cell.value = pat.sub(f"I{grand_row}", v)

    _relocate_profitability(ws)
    _highlight_profitability(ws)
    for cell in (ws["M8"], ws["N8"]):
        if isinstance(cell.value, str) and cell.value.startswith("="):
            cell.value = f'=IFERROR({cell.value[1:]},0)'
    from openpyxl.workbook.properties import CalcProperties
    wb.calculation = CalcProperties(calcId=0, fullCalcOnLoad=True, forceFullCalc=True)

    client = getattr(est, "client_name", None)
    if client:
        # Worksheet names have stricter rules than client names / filenames.
        ws.title = re.sub(r'[\\/*?:\[\]]', ' ', str(client))[:31].strip(" '") or "Client"

    wb.save(output_path)
    return output_path
