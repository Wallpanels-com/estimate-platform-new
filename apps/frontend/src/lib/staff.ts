import { referenceScene } from "./staffReferenceLayouts";
export type StaffStatus = "active" | "inactive" | "paused";
export type StaffMember = {
  id: string;
  avatar_url?: string | null;
  name: string;
  status: StaffStatus;
  title: string;
  department: string;
  fields: Record<string, string>;
  links: Record<string, string>;
  manager_id: string | null;
  version: number;
  updated_by: string;
  updated_at: string;
  source_row: number | null;
  source_sheet: string;
};
export type StaffDirectory = {
  items: StaffMember[];
  columns: Record<string, [string, string]>;
};
export type StaffLayout =
  | "tree"
  | "horizontal"
  | "orbit"
  | "departments"
  | "terraces"
  | "teams"
  | "holi"
  | "compact";
export const STAFF_WIDTH = 246;
export const STAFF_HEIGHT = 112;

/** Keep only actual reporting lines. Filtering walks up to the nearest visible ancestor. */
export function reportingParents(visible: StaffMember[], all: StaffMember[]) {
  const byId = new Map(all.map((p) => [p.id, p]));
  const ids = new Set(visible.map((p) => p.id));
  return new Map(
    visible.map((p) => {
      let parent = p.manager_id;
      const seen = new Set([p.id]);
      while (parent && !ids.has(parent) && !seen.has(parent)) {
        seen.add(parent);
        parent = byId.get(parent)?.manager_id || null;
      }
      return [p.id, parent && !seen.has(parent) ? parent : null];
    }),
  );
}

export function staffPositions(
  people: StaffMember[],
  parents: Map<string, string | null>,
  layout: StaffLayout,
) {
  if (layout === "teams" || layout === "holi" || layout === "compact")
    return referenceScene(people, parents, layout).positions;
  const positions = new Map<string, { x: number; y: number }>();
  const children = new Map<string, StaffMember[]>();
  const roots: StaffMember[] = [];
  for (const p of people) {
    const parent = parents.get(p.id);
    if (parent) children.set(parent, [...(children.get(parent) || []), p]);
    else roots.push(p);
  }
  const levels: StaffMember[][] = [];
  function level(p: StaffMember, depth: number) {
    if (positions.has(p.id)) return;
    positions.set(p.id, { x: 0, y: 0 });
    (levels[depth] ||= []).push(p);
    for (const child of children.get(p.id) || []) level(child, depth + 1);
  }
  roots.forEach((p) => level(p, 0));
  // Defensive fallback for malformed data; server rejects cycles at write time.
  for (const p of people) if (!positions.has(p.id)) level(p, 0);
  if (layout === "tree") {
    type Box = {
      width: number;
      height: number;
      entries: [string, number, number][];
    };
    function pack(p: StaffMember): Box {
      const kids = (children.get(p.id) || []).map(pack);
      if (!kids.length)
        return { width: 246, height: 112, entries: [[p.id, 0, 0]] };
      const lines: Box[][] = [];
      for (let i = 0; i < kids.length; i += 3) lines.push(kids.slice(i, i + 3));
      const width = Math.max(
        246,
        ...lines.map(
          (line) =>
            line.reduce((n, k) => n + k.width, 0) + (line.length - 1) * 40,
        ),
      );
      const entries: [string, number, number][] = [
        [p.id, (width - 246) / 2, 0],
      ];
      let y = 204;
      for (const line of lines) {
        const rowWidth =
          line.reduce((n, k) => n + k.width, 0) + (line.length - 1) * 40;
        let x = (width - rowWidth) / 2;
        for (const child of line) {
          entries.push(
            ...child.entries.map(
              ([id, cx, cy]) =>
                [id, cx + x, cy + y] as [string, number, number],
            ),
          );
          x += child.width + 40;
        }
        y += Math.max(...line.map((k) => k.height)) + 70;
      }
      return { width, height: y - 70, entries };
    }
    let x = 0;
    for (const root of roots) {
      const box = pack(root);
      for (const [id, cx, cy] of box.entries)
        positions.set(id, { x: cx + x, y: cy });
      x += box.width + 100;
    }
  } else if (layout === "horizontal") {
    let leaf = 0;
    function place(p: StaffMember, depth: number): number {
      const points = (children.get(p.id) || []).map((c) => place(c, depth + 1));
      const cross = points.length
        ? (points[0] + points[points.length - 1]) / 2
        : leaf++;
      positions.set(p.id, { x: depth * 354, y: cross * 146 });
      return cross;
    }
    roots.forEach((p) => {
      place(p, 0);
      leaf += 0.6;
    });
  } else if (layout === "orbit") {
    // Rings must remain separated even when a deep level contains most staff.
    let previous = 0;
    levels.forEach((group, depth) => {
      const radius =
        depth === 0 && group.length === 1
          ? 0
          : Math.max(previous + 430, (group.length * 310) / (2 * Math.PI));
      previous = radius;
      group.forEach((p, i) =>
        positions.set(p.id, {
          x: radius * Math.cos((2 * Math.PI * i) / group.length - Math.PI / 2),
          y: radius * Math.sin((2 * Math.PI * i) / group.length - Math.PI / 2),
        }),
      );
    });
  } else if (layout === "departments") {
    const departments = [
      ...new Set(people.map((p) => p.department || "—")),
    ].sort();
    let y = 0;
    for (let row = 0; row < departments.length; row += 3) {
      const chunk = departments.slice(row, row + 3);
      const groups = chunk.map((dept) =>
        people.filter((p) => (p.department || "—") === dept),
      );
      groups.forEach((group, col) =>
        group.forEach((p, i) =>
          positions.set(p.id, { x: col * 322, y: y + i * 150 }),
        ),
      );
      y += Math.max(...groups.map((group) => group.length)) * 150 + 100;
    }
  } else {
    // Terraces: broad layered galleries with fixed columns, rather than a long leaf tree.
    let y = 0;
    levels.forEach((group) => {
      const columns = Math.min(
        5,
        Math.max(1, Math.ceil(Math.sqrt(group.length * 1.6))),
      );
      group.forEach((p, i) =>
        positions.set(p.id, {
          x: (i % columns) * 298 + (5 - columns) * 149,
          y: y + Math.floor(i / columns) * 155,
        }),
      );
      y += Math.ceil(group.length / columns) * 155 + 145;
    });
  }
  return positions;
}
