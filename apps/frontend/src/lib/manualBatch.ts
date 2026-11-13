export interface BatchRow {
  id: string;
  name: string;
  section: string;
  description: string;
  quantity: string;
  unit: "ea" | "SF" | "LF";
  unit_price: string;
  total_price: string;
  accept_total: boolean;
  review: boolean;
  source: string;
}
export function blankRow(section = "General"): BatchRow {
  return {
    id: crypto.randomUUID(),
    name: "",
    section,
    description: "",
    quantity: "",
    unit: "ea",
    unit_price: "",
    total_price: "",
    accept_total: false,
    review: false,
    source: "",
  };
}
// Parse explicitly supported decimal / thousands conventions; never evaluate text.
export function decimal(value: string): string | null {
  let s = value
    .trim()
    .replace(/^\$\s*/, "")
    .replace(/\s*\$$/, "")
    .replace(/\u00a0/g, " ");
  if (/^\d{1,3}(?:[ ,]\d{3})+(?:\.\d{1,2})?$/.test(s))
    s = s.replace(/[ ,]/g, "");
  else if (/^\d{1,3}(?:[ .]\d{3})+,\d{1,2}$/.test(s))
    s = s.replace(/[ .]/g, "").replace(",", ".");
  else if (/^\d+(?:[.,]\d{1,2})?$/.test(s)) s = s.replace(",", ".");
  else return null;
  const valueNumber = Number(s);
  if (!Number.isFinite(valueNumber) || valueNumber > 9999999999.99) return null;
  return valueNumber.toFixed(2);
}
export function cents(value: string): bigint | null {
  const n = decimal(value);
  return n === null ? null : BigInt(n.replace(".", ""));
}
export function calculation(row: BatchRow): string | null {
  const q = cents(row.quantity),
    r = cents(row.unit_price);
  if (q === null || r === null || q > 9999999999n) return null;
  const total = (q * r + 50n) / 100n;
  if (total > 999999999999n) return null;
  return `${total / 100n}.${String(total % 100n).padStart(2, "0")}`;
}
export function mismatch(row: BatchRow) {
  const expected = calculation(row),
    entered = decimal(row.total_price);
  return expected !== null && entered !== null && expected !== entered;
}
export function rowError(row: BatchRow): string | null {
  if (!row.name.trim()) return "Enter an item name.";
  if (row.name.trim().length > 500)
    return "Use up to 500 characters for an item name.";
  if (!row.section.trim()) return "Enter a section.";
  if (decimal(row.total_price) === null) return "Enter a valid amount.";
  if (row.quantity || row.unit_price) {
    if (calculation(row) === null) return "Check quantity and unit price.";
    if (mismatch(row) && !row.accept_total)
      return "The calculation differs. Choose which total to use.";
  }
  if (row.review) return "Check this line and confirm it.";
  return null;
}
export function payloadRow(row: BatchRow) {
  return {
    name: row.name.trim(),
    section: row.section.trim(),
    description: row.description,
    unit: row.unit,
    quantity: row.quantity ? decimal(row.quantity) : null,
    unit_price: row.unit_price ? decimal(row.unit_price) : null,
    total_price: decimal(row.total_price),
    accept_total: row.accept_total,
  };
}
export type BatchPayload = {
  request_id: string;
  rows: ReturnType<typeof payloadRow>[];
};
export function parseList(text: string): BatchRow[] {
  const lines = text
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (lines.length > 200 || text.length > 100000)
    throw new Error("Use up to 200 lines at a time.");
  const rows: BatchRow[] = [];
  let section = "General";
  for (const raw of lines) {
    if (/^[^:]{1,120}\s*:$/.test(raw)) {
      section = raw.slice(0, -1).trim();
      continue;
    }
    const row = blankRow(section);
    row.source = raw;
    row.review = /[?？]/.test(raw);
    const line = raw.replace(/\?+\s*$/, "").replace(/^\s*[•●]\s*/, "");
    // Rightmost delimiter keeps hyphens and numeric model names intact.
    const match =
      /^(.*)\s+(?:[-–—:]\s+|\t)(.+)$/.exec(line) || /^(.*?)\t+(.+)$/.exec(line);
    if (!match) {
      row.name = line;
      row.review = true;
      rows.push(row);
      continue;
    }
    row.name = match[1].trim();
    const cost = match[2].trim();
    const expr =
      /^([\d., ]+)\s*(Lin(?:ear)?(?:\s*(?:ft|feet))?|LF|SF|sq\.?\s*ft|sqft|ea|pcs?)?\s*[x×*]\s*(\$?[\d., ]+)\s*(?:=\s*(\$?[\d., ]+))?$/i.exec(
        cost,
      );
    if (expr) {
      row.quantity = decimal(expr[1]) ?? "";
      row.unit = /^(lin|lf)/i.test(expr[2] || "")
        ? "LF"
        : /^(sf|sq)/i.test(expr[2] || "")
          ? "SF"
          : "ea";
      row.unit_price = decimal(expr[3]) ?? "";
      row.total_price = expr[4]
        ? (decimal(expr[4]) ?? "")
        : (calculation(row) ?? "");
      if (!row.quantity || !row.unit_price || !row.total_price)
        row.review = true;
    } else {
      row.total_price = decimal(cost) ?? "";
      if (!row.total_price) {
        row.name = line;
        row.review = true;
      }
    }
    if (raw.length > 500) row.review = true;
    rows.push(row);
  }
  return rows;
}

export type AIParsedRow = Pick<
  BatchRow,
  | "name"
  | "section"
  | "quantity"
  | "unit"
  | "unit_price"
  | "total_price"
  | "source"
>;
export type ParseBatch = (text: string) => Promise<{ rows: AIParsedRow[] }>;
