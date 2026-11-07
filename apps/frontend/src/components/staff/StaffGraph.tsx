import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ReactFlow,
  BaseEdge,
  getSmoothStepPath,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Handle,
  Position,
  MarkerType,
  applyNodeChanges,
  type EdgeProps,
  type NodeProps,
  type Node,
  type Edge,
  type NodeChange,
  type Connection,
} from "@xyflow/react";
import {
  ArrowUpRight,
  GripVertical,
  Pencil,
  Save,
  Undo2,
  Redo2,
  Trash2,
  RotateCcw,
  Check,
  Link2,
  GitBranch,
  X,
  LockKeyhole,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { request, errorMessage, ApiError } from "../../lib/api";
import { Button, ErrorNotice, useNotice } from "../ui";
import {
  reportingParents,
  staffPositions,
  type StaffMember,
  type StaffLayout,
} from "../../lib/staff";
import {
  referenceGeometry,
  referenceScene,
  type ReferenceLayout,
} from "../../lib/staffReferenceLayouts";
import {
  chartDraft,
  canConnect,
  connectDraft,
  removeConnection,
  orderedStaff,
  reorderAfterDrop,
  chartChanges,
  type ChartDraft,
  type StaffChartConfig,
  type LinkKind,
  type Point,
} from "../../lib/staffChart";
import "@xyflow/react/dist/style.css";

type PersonData = {
  person: StaffMember;
  open: (p: StaffMember) => void;
  ru: boolean;
  editing: boolean;
  layout: StaffLayout;
  indirect: boolean;
  childCount: number;
} & Record<string, unknown>;
type PersonNode = Node<PersonData, "person">;
type FrameNode = Node<{ label: string }, "department">;
type ChartNode = PersonNode | FrameNode;
const reference = (layout: StaffLayout): layout is ReferenceLayout =>
  ["teams", "holi", "compact"].includes(layout);
const Person = memo(function Person({ data }: NodeProps<PersonNode>) {
  const p = data.person;
  const newer = reference(data.layout);
  const holi = data.layout === "holi" || data.layout === "compact";
  const status =
    p.status === "active"
      ? data.ru
        ? "Работает"
        : "Active"
      : p.status === "paused"
        ? data.ru
          ? "На паузе"
          : "Paused"
        : data.ru
          ? "Не работает"
          : "Inactive";
  const body = (
    <>
      <span className="staff-person-top">
        <span className="staff-avatar">
          {p.name
            .split(/\s+/)
            .slice(0, 2)
            .map((n) => n[0])
            .join("")}
        </span>
        <span className={`staff-status-dot ${p.status}`} />
        {data.editing ? <GripVertical size={16} /> : <ArrowUpRight size={15} />}
      </span>
      <span className="staff-person-identity">
        <strong>{p.name}</strong>
        <span className="staff-person-title">{p.title || "—"}</span>
      </span>
      {data.layout === "teams" ? (
        <span className={`staff-status staff-status-${p.status}`}>
          {status}
        </span>
      ) : (
        !holi && (
          <span className="staff-person-dept">{p.department || "—"}</span>
        )
      )}
    </>
  );
  return (
    <div
      className={`staff-person staff-person-${p.status} ${newer ? "staff-person-reference" : ""} ${data.editing ? "staff-person-editing" : ""}`}
    >
      <Handle
        id="in"
        type="target"
        position={Position.Top}
        isConnectable={data.editing}
        role="button"
        tabIndex={data.editing ? 0 : -1}
        aria-label={`${data.ru ? "Входящая связь" : "Incoming connection"}: ${p.name}`}
      />
      {data.editing ? (
        <div className="staff-person-open staff-drag-handle">{body}</div>
      ) : (
        <button
          type="button"
          className="staff-person-open nodrag nopan"
          onClick={(e) => {
            e.stopPropagation();
            data.open(p);
          }}
          aria-label={`${data.ru ? "Открыть карточку" : "Open employee"}: ${p.name}`}
        >
          {body}
        </button>
      )}
      {(newer || data.editing) && (
        <button
          type="button"
          className="staff-person-details nodrag nopan"
          onClick={(e) => {
            e.stopPropagation();
            data.open(p);
          }}
        >
          {data.ru ? "Детали" : "Details"}
          <ArrowUpRight size={12} />
        </button>
      )}
      <Handle
        id="out"
        type="source"
        position={Position.Bottom}
        isConnectable={data.editing}
        role="button"
        tabIndex={data.editing ? 0 : -1}
        aria-label={`${data.ru ? "Исходящая связь" : "Outgoing connection"}: ${p.name}`}
      />
    </div>
  );
});
const Department = memo(function Department({ data }: NodeProps<FrameNode>) {
  return (
    <div className="staff-department-frame">
      <strong>{data.label}</strong>
    </div>
  );
});
const nodeTypes = { person: Person, department: Department };
function ReportingEdge(props: EdgeProps) {
  const bus = props.data?.busX as number | undefined;
  const [normal] = getSmoothStepPath({ ...props, borderRadius: 7, offset: 28 });
  const path =
    bus === undefined
      ? normal
      : `M ${props.sourceX},${props.sourceY} V ${props.sourceY + 28} H ${bus} V ${props.targetY - 28} H ${props.targetX} V ${props.targetY}`;
  const count = props.data?.badge as number | undefined;
  return (
    <>
      <BaseEdge
        path={path}
        style={props.style}
        markerEnd={props.markerEnd}
        interactionWidth={24}
      />
      {count && (
        <g
          className="staff-edge-count"
          transform={`translate(${props.sourceX},${props.sourceY + 34})`}
        >
          <circle r="15" />
          <text textAnchor="middle" dominantBaseline="central">
            {count}
          </text>
        </g>
      )}
    </>
  );
}
const edgeTypes = { staffReporting: ReportingEdge };
const emptyConfig: StaffChartConfig = {
  version: 0,
  extra_edges: [],
  orders: {},
  updated_by: "",
  updated_at: null,
};
export default function StaffGraph({
  people,
  all,
  layout,
  open,
  ru,
  onDirtyChange,
  onEditStart,
  onDepartment,
  department = "",
}: {
  people: StaffMember[];
  all: StaffMember[];
  layout: StaffLayout;
  open: (p: StaffMember) => void;
  ru: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onEditStart?: () => void;
  onDepartment?: (value: string) => void;
  department?: string;
}) {
  const L = (en: string, r: string) => (ru ? r : en);

  const client = useQueryClient();
  const notify = useNotice();
  const config = useQuery({
    queryKey: ["hr-staff-chart"],
    queryFn: () => request<StaffChartConfig>("/hr/staff/chart"),
  });
  const baseline = useMemo(
    () => chartDraft(all, config.data || emptyConfig),
    [all, config.data],
  );
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    if (!expanded) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const exit = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", exit);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", exit);
    };
  }, [expanded]);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ChartDraft | null>(null);
  const [past, setPast] = useState<ChartDraft[]>([]);
  const [future, setFuture] = useState<ChartDraft[]>([]);
  const [kind, setKind] = useState<LinkKind>("reporting");
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [alignment, setAlignment] = useState(0);
  const initial = useRef<{
    staff: StaffMember[];
    config: StaffChartConfig;
    draft: ChartDraft;
  } | null>(null);
  const current = editing && draft ? draft : baseline;
  const dirty =
    editing &&
    !!initial.current &&
    JSON.stringify(current) !== JSON.stringify(initial.current.draft);
  useEffect(() => {
    onDirtyChange?.(dirty);
    return () => onDirtyChange?.(false);
  }, [dirty, onDirtyChange]);
  useEffect(() => {
    if (!dirty) return;
    const guard = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [dirty]);
  const effectiveAll = useMemo(
    () =>
      all.map((p) => ({
        ...p,
        manager_id:
          p.id in current.managers ? current.managers[p.id] : p.manager_id,
      })),
    [all, current.managers],
  );
  const visibleIds = useMemo(() => new Set(people.map((p) => p.id)), [people]);
  const arranged = useMemo(
    () =>
      orderedStaff(
        effectiveAll.filter((p) => visibleIds.has(p.id)),
        current.orders[layout],
      ),
    [effectiveAll, visibleIds, current.orders, layout],
  );
  const parents = useMemo(
    () => reportingParents(arranged, effectiveAll),
    [arranged, effectiveAll],
  );
  const scene = useMemo(
    () =>
      reference(layout)
        ? referenceScene(arranged, parents, layout)
        : { positions: staffPositions(arranged, parents, layout), groups: [] },
    [arranged, parents, layout],
  );
  const positions = scene.positions;
  const geometry = reference(layout)
    ? referenceGeometry(layout)
    : { width: 246, height: editing ? 140 : 112 };
  // The classic layouts retain their regular cell spacing when the edit footer is visible.
  const targetNodes = useMemo<ChartNode[]>(
    () => [
      ...scene.groups.map((frame) => ({
        id: frame.id,
        type: "department" as const,
        position: { x: frame.x, y: frame.y },
        style: { width: frame.width, height: frame.height },
        data: { label: frame.label },
        selectable: false,
        draggable: false,
        connectable: false,
        zIndex: -1,
      })),
      ...arranged.map((p) => ({
        id: p.id,
        type: "person" as const,
        position: positions.get(p.id) || { x: 0, y: 0 },
        style: { width: geometry.width, height: geometry.height },
        dragHandle: ".staff-drag-handle",
        draggable: editing && !busy,
        connectable: editing && !busy,
        selectable: editing,
        zIndex: 2,
        data: {
          person: p,
          open,
          ru,
          editing: editing && !busy,
          layout,
          indirect: !!parents.get(p.id) && parents.get(p.id) !== p.manager_id,
          childCount: effectiveAll.filter((c) => c.manager_id === p.id).length,
        },
      })),
    ],
    [
      scene,
      arranged,
      positions,
      geometry.width,
      geometry.height,
      editing,
      busy,
      open,
      ru,
      layout,
      parents,
      effectiveAll,
    ],
  );
  const [nodes, setNodes] = useState<ChartNode[]>(targetNodes);
  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;
  const dragging = useRef(false);
  const animation = useRef<number>();
  useEffect(() => {
    if (animation.current) cancelAnimationFrame(animation.current);
    if (dragging.current) return;
    const reduced = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const from = new Map(nodesRef.current.map((n) => [n.id, n.position]));
    const start = performance.now();
    if (reduced || !nodesRef.current.length) {
      setNodes(targetNodes);
      return;
    }
    const frame = (now: number) => {
      const progress = Math.min(1, (now - start) / 280);
      const eased = 1 - Math.pow(1 - progress, 3);
      setNodes(
        targetNodes.map((node) => {
          const point = from.get(node.id) || node.position;
          return {
            ...node,
            position: {
              x: point.x + (node.position.x - point.x) * eased,
              y: point.y + (node.position.y - point.y) * eased,
            },
          };
        }),
      );
      if (progress < 1) animation.current = requestAnimationFrame(frame);
    };
    animation.current = requestAnimationFrame(frame);
    return () => {
      if (animation.current) cancelAnimationFrame(animation.current);
    };
  }, [targetNodes, alignment]);
  const commit = useCallback(
    (next: ChartDraft) => {
      if (JSON.stringify(next) === JSON.stringify(current)) return;
      setPast((p) => [...p, current].slice(-40));
      setFuture([]);
      setDraft(next);
      setSelected(null);
      setError("");
    },
    [current],
  );
  const edgeData = useMemo<Edge[]>(() => {
    const reporting = arranged.flatMap((p) => {
      const source = parents.get(p.id);
      if (!source) return [];
      const indirect = source !== p.manager_id;
      const siblings = arranged.filter((c) => parents.get(c.id) === source);
      const multirow =
        new Set(siblings.map((c) => positions.get(c.id)?.y)).size > 1;
      const busX =
        layout === "tree" && multirow
          ? Math.min(...siblings.map((c) => positions.get(c.id)?.x || 0)) - 30
          : layout === "compact" && siblings.length > 1
            ? Math.max(...siblings.map((c) => positions.get(c.id)?.x || 0)) +
              geometry.width +
              45
            : undefined;
      const id = "reporting:" + p.id;
      return [
        {
          id,
          source,
          target: p.id,
          sourceHandle: "out",
          targetHandle: "in",
          type: "staffReporting",
          selectable: editing && !indirect,
          zIndex: 1,
          data: {
            kind: "reporting",
            indirect,
            busX,
            badge:
              (layout === "holi" || layout === "compact") &&
              siblings[0]?.id === p.id
                ? siblings.length
                : undefined,
          },
          className: indirect ? "staff-edge-indirect" : "staff-edge",
          style: { strokeWidth: selected === id ? 3 : 1.4 },
          selected: selected === id,
        },
      ];
    });
    const additional = current.extra_edges
      .filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target))
      .map((e) => {
        const id = `additional:${e.source}:${e.target}`;
        return {
          ...e,
          id,
          sourceHandle: "out",
          targetHandle: "in",
          type: "default",
          selectable: editing,
          zIndex: 1,
          data: { kind: "additional" },
          className: "staff-edge-additional",
          style: { strokeWidth: selected === id ? 3 : 1.6 },
          selected: selected === id,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 14,
            height: 14,
            color: "#4583bd",
          },
        };
      });
    return [...reporting, ...additional];
  }, [
    arranged,
    parents,
    positions,
    layout,
    geometry.width,
    editing,
    current.extra_edges,
    visibleIds,
    selected,
  ]);
  function startEditing() {
    if (!config.data) return;
    const next = chartDraft(all, config.data);
    initial.current = {
      staff: all.map((p) => ({ ...p })),
      config: config.data,
      draft: next,
    };
    setDraft(next);
    setPast([]);
    setFuture([]);
    setEditing(true);
    setError("");
    onEditStart?.();
  }
  function cancel() {
    setEditing(false);
    setDraft(null);
    setPast([]);
    setFuture([]);
    setSelected(null);
    setError("");
    void client.invalidateQueries({ queryKey: ["hr-staff"] });
    void config.refetch();
  }
  async function save() {
    if (!initial.current || !dirty || busy) return;
    setBusy(true);
    setError("");
    try {
      await request("/hr/staff/chart", {
        method: "PUT",
        body: JSON.stringify({
          version: initial.current.config.version,
          changes: chartChanges(current, initial.current.staff),
          extra_edges: current.extra_edges,
          orders: current.orders,
        }),
      });
      await Promise.all([
        client.invalidateQueries({ queryKey: ["hr-staff"] }),
        client.invalidateQueries({ queryKey: ["hr-staff-chart"] }),
      ]);
      setEditing(false);
      setDraft(null);
      setPast([]);
      setFuture([]);
      setSelected(null);
      notify(L("Organization chart saved", "Схема сохранена"));
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 409
          ? L(
              "The saved data has changed. Your draft is preserved. Cancel and reopen editing to load the current version.",
              "Сохранённые данные изменились. Черновик оставлен на экране. Отмените его и заново откройте редактор, чтобы загрузить актуальную версию.",
            )
          : errorMessage(e),
      );
    } finally {
      setBusy(false);
    }
  }
  function undo() {
    const previous = past.at(-1);
    if (!previous || busy) return;
    setFuture((f) => [current, ...f]);
    setDraft(previous);
    setPast((p) => p.slice(0, -1));
    setSelected(null);
    setError("");
  }
  function redo() {
    if (!future.length || busy) return;
    setPast((p) => [...p, current]);
    setDraft(future[0]);
    setFuture((f) => f.slice(1));
    setSelected(null);
    setError("");
  }
  function deleteSelected() {
    const edge = edgeData.find((e) => e.id === selected);
    if (!edge || edge.data?.indirect || busy) return;
    commit(
      removeConnection(
        current,
        edge.source,
        edge.target,
        edge.data?.kind as LinkKind,
      ),
    );
  }
  const valid = useCallback(
    (connection: Connection | Edge) =>
      !!connection.source &&
      !!connection.target &&
      canConnect(current, connection.source, connection.target, kind),
    [current, kind],
  );
  const color = useCallback(
    (node: Node) =>
      node.type === "department"
        ? "transparent"
        : (node.data as PersonData).person.status === "active"
          ? "#8b80d1"
          : "#c5c6d0",
    [],
  );
  const onChanges = useCallback(
    (changes: NodeChange<ChartNode>[]) =>
      setNodes((ns) => applyNodeChanges(changes, ns)),
    [],
  );
  const selectedEdge = edgeData.find((e) => e.id === selected);
  const personIds = arranged
    .map((p) => p.id)
    .sort()
    .join();
  return (
    <div
      className={`staff-graph-shell ${expanded ? "staff-graph-expanded" : ""}`}
    >
      <div className="staff-graph-toolbar">
        <Button
          variant="ghost"
          aria-label={
            expanded
              ? L("Close full screen", "Закрыть полный экран")
              : L("Open full screen", "Открыть на весь экран")
          }
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
        </Button>
        {!editing ? (
          <>
            <span className="staff-graph-readonly">
              <LockKeyhole size={14} />
              {L("Saved organization chart", "Сохранённая схема")}
            </span>
            <Button
              onClick={startEditing}
              disabled={!config.data || !!config.error}
            >
              <Pencil size={16} />
              {L("Edit chart", "Редактировать схему")}
            </Button>
          </>
        ) : (
          <>
            <div
              className="staff-link-kind"
              role="group"
              aria-label={L("Connection type", "Тип связи")}
            >
              <button
                disabled={busy}
                aria-pressed={kind === "reporting"}
                onClick={() => setKind("reporting")}
              >
                <GitBranch size={15} />
                {L("Reporting", "Подчинение")}
              </button>
              <button
                disabled={busy}
                aria-pressed={kind === "additional"}
                onClick={() => setKind("additional")}
              >
                <Link2 size={15} />
                {L("Additional", "Доп. связь")}
              </button>
            </div>
            <Button
              variant="ghost"
              aria-label={L("Undo chart change", "Отменить действие")}
              disabled={!past.length || busy}
              onClick={undo}
            >
              <Undo2 size={17} />
            </Button>
            <Button
              variant="ghost"
              aria-label={L("Redo chart change", "Повторить действие")}
              disabled={!future.length || busy}
              onClick={redo}
            >
              <Redo2 size={17} />
            </Button>
            <Button
              variant="ghost"
              disabled={!selectedEdge || busy}
              onClick={deleteSelected}
            >
              <Trash2 size={16} />
              {L("Delete connection", "Удалить связь")}
            </Button>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => {
                const orders = { ...current.orders };
                delete orders[layout];
                commit({ ...current, orders });
                setAlignment((v) => v + 1);
              }}
            >
              <RotateCcw size={15} />
              {L("Auto arrange", "Выровнять")}
            </Button>
            <span className="staff-draft-state">
              {dirty
                ? L("Unsaved changes", "Есть изменения")
                : L(
                    "Drag cards or connect the circles",
                    "Двигайте карточки или соединяйте точки",
                  )}
            </span>
            <Button disabled={busy} onClick={cancel}>
              {L("Cancel", "Отмена")}
            </Button>
            <Button
              variant="primary"
              busy={busy}
              disabled={!dirty}
              onClick={() => void save()}
            >
              <Save size={16} />
              {L("Save chart", "Сохранить схему")}
            </Button>
          </>
        )}
      </div>
      {config.error && (
        <ErrorNotice retry={() => void config.refetch()}>
          {L(
            "Chart settings could not be loaded. Try again.",
            "Не удалось загрузить настройки схемы. Попробуйте ещё раз.",
          )}
        </ErrorNotice>
      )}
      {error && <ErrorNotice>{error}</ErrorNotice>}
      {editing && (
        <p className="staff-editor-help">
          {L(
            "Drag from a bottom circle to a top circle. Solid lines set the manager; dashed lines add a separate connection. Drag cards to reorder peers; they align automatically.",
            "Тяните линию от нижнего кружка к верхнему. Сплошная — подчинение, пунктир — дополнительная связь. Перетаскивайте карточки, чтобы менять порядок на уровне: сетка выровняется автоматически.",
          )}
        </p>
      )}
      <section
        className={`staff-canvas staff-canvas-${layout} ${editing ? "staff-canvas-editing" : ""}`}
        aria-label={L("Organization chart", "Организационная структура")}
        tabIndex={editing ? 0 : undefined}
        onKeyDown={(e) => {
          if (
            !editing ||
            busy ||
            e.target instanceof HTMLInputElement ||
            e.target instanceof HTMLTextAreaElement
          )
            return;
          if (e.key === "Delete" || e.key === "Backspace") {
            e.preventDefault();
            deleteSelected();
          }
          if (e.key === "Escape") setSelected(null);
        }}
      >
        <div className="staff-canvas-caption">
          <span className="staff-live-dot" />
          {L("TEAM STRUCTURE", "СХЕМА КОМАНДЫ")}
          <span>
            {people.length} {L("people", "сотрудников")}
          </span>
        </div>
        {layout === "teams" && onDepartment && (
          <nav
            className="staff-scene-departments"
            aria-label={L("Chart departments", "Отделы на схеме")}
          >
            <button aria-pressed={!department} onClick={() => onDepartment("")}>
              {L("All departments", "Все отделы")}
            </button>
            {[...new Set(all.map((p) => p.department))].sort().map((d) => (
              <button
                key={d}
                aria-pressed={department === d}
                onClick={() => onDepartment(d)}
              >
                {d}
              </button>
            ))}
          </nav>
        )}
        {!people.length && (
          <div className="staff-chart-empty">
            {L(
              "No employees match these filters. Clear a filter to continue.",
              "Нет сотрудников по выбранным фильтрам. Измените фильтр.",
            )}
          </div>
        )}
        <ReactFlow<ChartNode>
          key={`${layout}-${personIds}-${expanded}`}
          nodes={nodes}
          edges={edgeData}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onNodesChange={onChanges}
          nodesDraggable={editing && !busy}
          nodesConnectable={editing && !busy}
          edgesReconnectable={false}
          elementsSelectable={editing}
          deleteKeyCode={null}
          onInit={(instance) => {
            // Fit the target scene rather than stale nodes during a filter transition.
            requestAnimationFrame(() =>
              requestAnimationFrame(() => {
                const canvas = document
                  .querySelector(".staff-canvas")
                  ?.getBoundingClientRect();
                const height = canvas?.height || 600;
                const width = canvas?.width || 1100;
                if (people.length <= 12 && targetNodes.length) {
                  const minX = Math.min(
                    ...targetNodes.map((n) => n.position.x),
                  );
                  const minY = Math.min(
                    ...targetNodes.map((n) => n.position.y),
                  );
                  const maxX = Math.max(
                    ...targetNodes.map(
                      (n) =>
                        n.position.x + Number(n.style?.width || geometry.width),
                    ),
                  );
                  const maxY = Math.max(
                    ...targetNodes.map(
                      (n) =>
                        n.position.y +
                        Number(n.style?.height || geometry.height),
                    ),
                  );
                  const left = layout === "teams" ? 210 : 45;
                  const top = 90;
                  const availableW = Math.max(100, width - left - 45);
                  const availableH = Math.max(100, height - top - 70);
                  const zoom = Math.max(
                    0.06,
                    Math.min(
                      1,
                      availableW / Math.max(1, maxX - minX),
                      availableH / Math.max(1, maxY - minY),
                    ),
                  );
                  void instance.setViewport({
                    x:
                      left +
                      (availableW - (maxX - minX) * zoom) / 2 -
                      minX * zoom,
                    y:
                      top +
                      (availableH - (maxY - minY) * zoom) / 2 -
                      minY * zoom,
                    zoom,
                  });
                  return;
                }
                const root = arranged.find((p) => !parents.get(p.id));
                const point = root && positions.get(root.id);
                const zoom = 0.8;
                if (point)
                  void instance.setCenter(
                    point.x + geometry.width / 2,
                    point.y + height / (2 * zoom) - 150 / zoom,
                    { zoom },
                  );
              }),
            );
          }}
          minZoom={0.06}
          maxZoom={1.5}
          preventScrolling={false}
          zoomOnScroll={false}
          zoomOnDoubleClick={false}
          attributionPosition="top-right"
          snapToGrid
          snapGrid={[20, 20]}
          onNodeClick={(_, node) => {
            setSelected(null);
            if (!editing && node.type === "person") open(node.data.person);
          }}
          onPaneClick={() => setSelected(null)}
          onEdgeClick={(event, edge) => {
            if (editing && !edge.data?.indirect) {
              event.stopPropagation();
              setSelected(edge.id);
            }
          }}
          isValidConnection={valid}
          onConnect={(connection) => {
            if (connection.source && connection.target)
              commit(
                connectDraft(
                  current,
                  connection.source,
                  connection.target,
                  kind,
                ),
              );
          }}
          onConnectEnd={(_, state) => {
            if (state.toNode && !state.isValid)
              setError(
                L(
                  "This reporting link would form a cycle or duplicate a connection. Choose Additional for cross-team links.",
                  "Такая связь создаёт цикл подчинения или уже существует. Для связей между коллегами выберите «Доп. связь».",
                ),
              );
          }}
          onNodeDragStart={() => {
            dragging.current = true;
            if (animation.current) cancelAnimationFrame(animation.current);
            setSelected(null);
          }}
          onNodeDragStop={(_, node) => {
            dragging.current = false;
            commit(
              reorderAfterDrop(
                current,
                all,
                arranged,
                positions,
                node.id,
                node.position,
                layout,
              ),
            );
            setAlignment((v) => v + 1);
          }}
        >
          <Background
            variant={
              layout === "teams"
                ? BackgroundVariant.Lines
                : BackgroundVariant.Dots
            }
            gap={layout === "teams" ? 160 : 22}
            size={layout === "teams" ? 1.2 : 0.8}
            color={
              layout === "orbit"
                ? "#324754"
                : layout === "teams"
                  ? "#c4c5d0"
                  : "#c7cad6"
            }
          />
          <Controls showInteractive={false} />
          <MiniMap
            style={{ width: 150, height: 95 }}
            nodeColor={color}
            pannable
            zoomable
            maskColor={
              layout === "orbit" ? "rgba(8,20,31,.65)" : "rgba(236,240,241,.65)"
            }
          />
        </ReactFlow>
        <span className="staff-canvas-tip">
          {editing
            ? L(
                "Bottom → top · Click a line → Delete · Save to apply changes",
                "Снизу → вверх · Выберите линию → Удалить · Сохраните изменения",
              )
            : L(
                "Drag the background to pan · Use + / − to zoom · Click a person for details",
                "Перетаскивайте фон · Масштаб + / − · Карточка сотрудника — по клику",
              )}
        </span>
      </section>
    </div>
  );
}
