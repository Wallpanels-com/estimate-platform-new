import type { StaffMember, StaffLayout } from "./staff";
export type ExtraConnection = { source: string; target: string };
export type StaffChartConfig = {
  version: number;
  extra_edges: ExtraConnection[];
  orders: Partial<Record<StaffLayout, string[]>>;
  updated_by: string;
  updated_at: string | null;
};
export type ChartDraft = {
  managers: Record<string, string | null>;
  extra_edges: ExtraConnection[];
  orders: Partial<Record<StaffLayout, string[]>>;
};
export type LinkKind = "reporting" | "additional";
export type Point = { x: number; y: number };
export function chartDraft(
  people: StaffMember[],
  config: StaffChartConfig,
): ChartDraft {
  return {
    managers: Object.fromEntries(people.map((p) => [p.id, p.manager_id])),
    // A manager can also be changed from the employee card. A former
    // collaboration edge then becomes the reporting edge, without a duplicate.
    extra_edges: config.extra_edges
      .filter(
        (e) =>
          !people.some((p) => p.id === e.target && p.manager_id === e.source),
      )
      .map((e) => ({ ...e })),
    orders: structuredClone(config.orders),
  };
}
export function canConnect(
  draft: ChartDraft,
  source: string,
  target: string,
  kind: LinkKind,
) {
  if (
    source === target ||
    !(source in draft.managers) ||
    !(target in draft.managers)
  )
    return false;
  if (kind === "additional")
    return (
      draft.managers[target] !== source &&
      !draft.extra_edges.some((e) => e.source === source && e.target === target)
    );
  if (draft.managers[target] === source) return false;
  const seen = new Set<string>();
  let parent: string | null = source;
  while (parent) {
    if (parent === target || seen.has(parent)) return false;
    seen.add(parent);
    parent = draft.managers[parent] || null;
  }
  return true;
}
export function connectDraft(
  draft: ChartDraft,
  source: string,
  target: string,
  kind: LinkKind,
): ChartDraft {
  if (!canConnect(draft, source, target, kind)) return draft;
  return kind === "reporting"
    ? {
        ...draft,
        managers: { ...draft.managers, [target]: source },
        extra_edges: draft.extra_edges.filter(
          (e) => !(e.source === source && e.target === target),
        ),
      }
    : { ...draft, extra_edges: [...draft.extra_edges, { source, target }] };
}
export function removeConnection(
  draft: ChartDraft,
  source: string,
  target: string,
  kind: LinkKind,
): ChartDraft {
  return kind === "reporting"
    ? { ...draft, managers: { ...draft.managers, [target]: null } }
    : {
        ...draft,
        extra_edges: draft.extra_edges.filter(
          (e) => !(e.source === source && e.target === target),
        ),
      };
}
export function orderedStaff(people: StaffMember[], order: string[] = []) {
  const ranks = new Map(order.map((id, i) => [id, i]));
  return [...people].sort(
    (a, b) =>
      (ranks.get(a.id) ?? 1e6) - (ranks.get(b.id) ?? 1e6) ||
      a.name.localeCompare(b.name) ||
      a.id.localeCompare(b.id),
  );
}
/** Drop changes sibling order, never an employee's manager/department or arbitrary coordinates. */
export function reorderAfterDrop(
  draft: ChartDraft,
  all: StaffMember[],
  visible: StaffMember[],
  positions: Map<string, Point>,
  id: string,
  drop: Point,
  layout: StaffLayout,
): ChartDraft {
  const current = orderedStaff(all, draft.orders[layout]);
  const siblings = visible.filter(
    (p) =>
      p.id !== id &&
      draft.managers[p.id] === draft.managers[id] &&
      positions.has(p.id),
  );
  if (!siblings.length) return draft;
  const nearest = [...siblings].sort((a, b) => {
    const pa = positions.get(a.id)!,
      pb = positions.get(b.id)!;
    return (
      Math.hypot(pa.x - drop.x, pa.y - drop.y) -
      Math.hypot(pb.x - drop.x, pb.y - drop.y)
    );
  })[0];
  const anchor = positions.get(nearest.id)!;
  const after =
    layout === "horizontal"
      ? drop.y > anchor.y
      : Math.abs(drop.y - anchor.y) > 65
        ? drop.y > anchor.y
        : drop.x > anchor.x;
  const ids = current.map((p) => p.id).filter((value) => value !== id);
  const index = ids.indexOf(nearest.id);
  ids.splice(index + (after ? 1 : 0), 0, id);
  if (ids.every((value, i) => value === current[i]?.id)) return draft;
  return { ...draft, orders: { ...draft.orders, [layout]: ids } };
}
export function chartChanges(draft: ChartDraft, baseline: StaffMember[]) {
  return baseline
    .filter((p) => draft.managers[p.id] !== p.manager_id)
    .map((p) => ({
      id: p.id,
      version: p.version,
      manager_id: draft.managers[p.id],
    }));
}
