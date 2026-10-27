"""Read-only checks of exported client-table cells and their Excel formulas."""
import ast
from decimal import Decimal, ROUND_HALF_UP
import re
from openpyxl import load_workbook


def cell_value(sheet, coordinate, stack=()):
    if coordinate in stack:
        raise AssertionError("Circular client-table formula: " + coordinate)
    value = sheet[coordinate].value
    if not isinstance(value, str) or not value.startswith("="):
        return Decimal(str(value or 0)) if not isinstance(value, str) else Decimal(0)
    expression = value[1:]
    expression = re.sub(r"SUM\(I(\d+):I(\d+)\)", lambda m: str(sum((cell_value(sheet, f"I{n}", (*stack, coordinate)) for n in range(int(m[1]), int(m[2])+1)), Decimal(0))), expression)
    expression = re.sub(r"\b[A-Z]+[0-9]+\b", lambda m: str(cell_value(sheet, m[0], (*stack, coordinate))), expression)
    def visit(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return Decimal(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -visit(node.operand)
        if isinstance(node, ast.BinOp):
            a, b = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return a+b
            if isinstance(node.op, ast.Sub): return a-b
            if isinstance(node.op, ast.Mult): return a*b
            if isinstance(node.op, ast.Div): return a/b
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ROUND" and len(node.args) == 2:
            return visit(node.args[0]).quantize(Decimal(10) ** -int(visit(node.args[1])), rounding=ROUND_HALF_UP)
        raise AssertionError("Unsupported client-table formula: " + expression)
    return visit(ast.parse(expression, mode="eval").body)


def check_passport(path, estimate):
    workbook = load_workbook(path)
    sheet = workbook.active
    assert sheet["C3"].value == estimate["client_name"]
    assert sheet["C9"].value == len(estimate["zones"])
    items = [i for z in estimate["zones"] for i in sorted(z["line_items"], key=lambda i:i["sort_order"])]
    items += [i for i in estimate["line_items"] if i["zone_id"] is None]
    rows = [row for row in sheet.iter_rows(min_row=19) if row[2].value is not None]
    assert len(rows) == len(items), (len(rows), len(items))
    for row, item in zip(rows, items):
        assert row[2].value == item["name"]
        for column, field in ((6, "unit_price"), (7, "quantity"), (8, "total_price")):
            if item.get(field) is not None:
                assert Decimal(str(row[column].value)) == Decimal(str(item[field])), (item["name"], field)
    grand = next(row[8].coordinate for row in sheet.iter_rows() if row[6].value == "TOTAL Estimate")
    raw = sum((Decimal(i["total_price"]) for i in items), Decimal(0))
    factor = (1 + Decimal(estimate.get("markup_pct") or 0)/100)*(1 - Decimal(estimate.get("discount_pct") or 0)/100)
    expected = (Decimal(estimate["final_total"]) * factor).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    assert cell_value(sheet, grand) == expected, (cell_value(sheet, grand), expected)
    assert raw == Decimal(estimate["subtotal"])
    assert workbook.calculation.fullCalcOnLoad
    assert not any("#REF!" in str(cell.value) for row in sheet for cell in row)
    return {"items": len(items), "zones": len(estimate["zones"]), "total": str(expected), "grand_cell": grand}
