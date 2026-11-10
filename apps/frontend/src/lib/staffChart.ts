import {
  reportingParents,
  staffPositions,
  type StaffMember,
  type StaffLayout,
} from "./staff";
export type ExtraConnection = { source: string; target: string };
export type ChartPositions = Partial<
  Record<StaffLayout, Record<string, Point>>
>;
export type StaffChartConfig = {
  version: number;
  extra_edges: ExtraConnection[];
  orders: Partial<Record<StaffLayout, string[]>>;
  positions?: ChartPositions;
  updated_by: string;
  updated_at: string | null;
};
export type ChartDraft = {
  managers: Record<string, string | null>;
  extra_edges: ExtraConnection[];
  orders: Partial<Record<StaffLayout, string[]>>;
  positions: ChartPositions;
};
export type LinkKind = "reporting" | "additional";
export type NewStaff = {
  id: string;
  name: string;
  status: "active" | "inactive" | "paused";
  title: string;
  department: string;
  manager_id: string | null;
  contact: string;
  email: string;
  notes: string;
};
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
    positions: structuredClone(config.positions || {}),
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
/** Reconnection is atomic in the draft; an invalid endpoint keeps the old line. */
export function reconnectDraft(
  draft: ChartDraft,
  source: string,
  target: string,
  nextSource: string,
  nextTarget: string,
  kind: LinkKind,
) {
  const without = removeConnection(draft, source, target, kind);
  return canConnect(without, nextSource, nextTarget, kind)
    ? connectDraft(without, nextSource, nextTarget, kind)
    : draft;
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
export function chartChanges(draft: ChartDraft, baseline: StaffMember[]) {
  return baseline
    .filter((p) => draft.managers[p.id] !== p.manager_id)
    .map((p) => ({
      id: p.id,
      version: p.version,
      manager_id: draft.managers[p.id],
    }));
}

/** Moving a card never changes its reporting line or triggers auto-layout. */
export function moveCard(
  draft: ChartDraft,
  layout: StaffLayout,
  id: string,
  point: Point,
): ChartDraft {
  if (
    !(id in draft.managers) ||
    !Number.isFinite(point.x) ||
    !Number.isFinite(point.y)
  )
    return draft;
  return {
    ...draft,
    positions: {
      ...draft.positions,
      [layout]: {
        ...draft.positions[layout],
        [id]: { x: point.x, y: point.y },
      },
    },
  };
}

/** Compact the visible team; park filtered-out cards below it, never on top. */
export function arrangeCards(
  draft: ChartDraft,
  all: StaffMember[],
  visibleIds: ReadonlySet<string>,
  layout: StaffLayout,
  cardHeight: number,
) {
  const ordered = orderedStaff(
    all.map((p) => ({ ...p, manager_id: draft.managers[p.id] ?? null })),
    draft.orders[layout],
  );
  const shown = ordered.filter((p) => visibleIds.has(p.id));
  const hidden = ordered.filter((p) => !visibleIds.has(p.id));
  const placed = staffPositions(
    shown,
    reportingParents(shown, ordered),
    layout,
  );
  const parked = staffPositions(
    hidden,
    reportingParents(hidden, ordered),
    layout,
  );
  const offset =
    placed.size && parked.size
      ? Math.max(...[...placed.values()].map((p) => p.y)) +
        cardHeight +
        200 -
        Math.min(...[...parked.values()].map((p) => p.y))
      : 0;
  for (const [id, point] of parked)
    placed.set(id, { x: point.x, y: point.y + offset });
  return {
    ...draft,
    positions: { ...draft.positions, [layout]: Object.fromEntries(placed) },
  };
}
