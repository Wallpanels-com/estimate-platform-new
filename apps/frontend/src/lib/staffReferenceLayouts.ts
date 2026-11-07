import type { StaffMember } from "./staff";
import type { Point } from "./staffChart";
export type ReferenceLayout = "teams" | "holi" | "compact";
export type StaffFrame = {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
};
export const referenceGeometry = (layout: ReferenceLayout) =>
  layout === "teams"
    ? { width: 300, height: 148 }
    : { width: 280, height: 132 };
type Box = {
  width: number;
  height: number;
  entries: [string, number, number][];
};
function forest(
  people: StaffMember[],
  parents: Map<string, string | null>,
  width: number,
  height: number,
  compact = false,
) {
  const ids = new Set(people.map((p) => p.id));
  const children = new Map<string, StaffMember[]>();
  const roots = people.filter((p) => !ids.has(parents.get(p.id) || ""));
  for (const p of people) {
    const parent = parents.get(p.id);
    if (parent && ids.has(parent))
      children.set(parent, [...(children.get(parent) || []), p]);
  }
  function pack(p: StaffMember): Box {
    const kids = children.get(p.id) || [];
    if (!kids.length) return { width, height, entries: [[p.id, 0, 0]] };
    if (compact && kids.every((k) => !(children.get(k.id) || []).length))
      return {
        width: width + 36,
        height: height + 100 + kids.length * (height + 52) - 52,
        entries: [
          [p.id, 0, 0],
          ...kids.map(
            (k, i) =>
              [k.id, 36, height + 100 + i * (height + 52)] as [
                string,
                number,
                number,
              ],
          ),
        ],
      };
    const boxes = kids.map(pack);
    const span =
      boxes.reduce((n, b) => n + b.width, 0) + (boxes.length - 1) * 90;
    const entries: [string, number, number][] = [[p.id, (span - width) / 2, 0]];
    let x = 0;
    for (const box of boxes) {
      entries.push(
        ...box.entries.map(
          ([id, cx, cy]) =>
            [id, cx + x, cy + height + 110] as [string, number, number],
        ),
      );
      x += box.width + 90;
    }
    return {
      width: span,
      height: height + 110 + Math.max(...boxes.map((b) => b.height)),
      entries,
    };
  }
  const positions = new Map<string, Point>();
  let x = 0;
  let totalHeight = 0;
  for (const root of roots) {
    const box = pack(root);
    for (const [id, cx, cy] of box.entries)
      positions.set(id, { x: cx + x, y: cy });
    x += box.width + 120;
    totalHeight = Math.max(totalHeight, box.height);
  }
  return { positions, width: Math.max(0, x - 120), height: totalHeight };
}
export function referenceScene(
  people: StaffMember[],
  parents: Map<string, string | null>,
  layout: ReferenceLayout,
) {
  const { width, height } = referenceGeometry(layout);
  if (layout !== "teams")
    return {
      ...forest(people, parents, width, height, layout === "compact"),
      groups: [] as StaffFrame[],
    };
  const trunk = people.filter(
    (p) =>
      !parents.get(p.id) || p.department.toLowerCase() === "administration",
  );
  const trunkIds = new Set(trunk.map((p) => p.id));
  const crown = forest(trunk, parents, width, height, false);
  const positions = new Map(crown.positions);
  const groups: StaffFrame[] = [];
  const departments = [
    ...new Set(
      people.filter((p) => !trunkIds.has(p.id)).map((p) => p.department || "—"),
    ),
  ];
  let y = crown.height ? crown.height + 180 : 0;
  let maxWidth = crown.width;
  for (let row = 0; row < departments.length; row += 2) {
    let x = 0;
    let rowHeight = 0;
    for (const department of departments.slice(row, row + 2)) {
      const members = people.filter(
        (p) => (p.department || "—") === department && !trunkIds.has(p.id),
      );
      const ids = new Set(members.map((p) => p.id));
      let heads = members.filter((p) => !ids.has(parents.get(p.id) || ""));
      let body = members.filter((p) => !heads.some((h) => h.id === p.id));
      if (!body.length) {
        body = members;
        heads = [];
      }
      const columns = Math.min(
        body.length > 6 ? 3 : 2,
        Math.max(1, body.length),
      );
      const frameWidth = Math.max(
        columns * (width + 28) + 28,
        heads.length * (width + 28) + 28,
      );
      const headY = y;
      const frameY = y + (heads.length ? height + 84 : 0);
      heads.forEach((p, i) =>
        positions.set(p.id, {
          x:
            x +
            (frameWidth - heads.length * (width + 28)) / 2 +
            i * (width + 28),
          y: headY,
        }),
      );
      const frameHeight = Math.ceil(body.length / columns) * (height + 28) + 50;
      body.forEach((p, i) =>
        positions.set(p.id, {
          x: x + 28 + (i % columns) * (width + 28),
          y: frameY + 56 + Math.floor(i / columns) * (height + 28),
        }),
      );
      groups.push({
        id: "department:" + department,
        label: department,
        x,
        y: frameY,
        width: frameWidth,
        height: frameHeight + 16,
      });
      x += frameWidth + 100;
      rowHeight = Math.max(rowHeight, frameY - y + frameHeight + 16);
    }
    maxWidth = Math.max(maxWidth, x - 100);
    y += rowHeight + 150;
  }
  // Centre the actual top management over the department panels.
  const offset = Math.max(0, (maxWidth - crown.width) / 2);
  for (const p of trunk) {
    const point = positions.get(p.id);
    if (point) positions.set(p.id, { x: point.x + offset, y: point.y });
  }
  return { positions, groups, width: maxWidth, height: y };
}
