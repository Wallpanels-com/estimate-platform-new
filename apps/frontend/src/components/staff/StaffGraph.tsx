import StaffAvatar from "./StaffAvatar";
import StaffHierarchy from "./StaffHierarchy";
import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ReactFlow,
  Panel,
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
  type ReactFlowInstance,
  type EdgeProps,
  type NodeProps,
  type Node,
  type Edge,
  type NodeChange,
  type Connection,
  type OnConnectEnd,
} from "@xyflow/react";
import {
  ArrowUpRight,
  GripVertical,
  Save,
  Undo2,
  Redo2,
  Trash2,
  RotateCcw,
  Pencil,
  Link2,
  GitBranch,
  X,
  Maximize2,
  Minimize2,
} from "lucide-react";
import { request, errorMessage, ApiError } from "../../lib/api";
import { Button, ErrorNotice, ModalPresence, useNotice } from "../ui";
import StaffCreate from "./StaffCreate";
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
  reconnectDraft,
  orderedStaff,
  moveCard,
  arrangeCards,
  chartChanges,
  type ChartDraft,
  type StaffChartConfig,
  type LinkKind,
  type Point,
  type NewStaff,
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
        <StaffAvatar person={p} />
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
  departments,
  layout,
  open,
  ru,
  onDirtyChange,
  onEditStart,
  onDepartment,
  department = "",
  onCreated,
}: {
  people: StaffMember[];
  all: StaffMember[];
  departments: string[];
  layout: StaffLayout;
  open: (p: StaffMember) => void;
  ru: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onEditStart?: () => void;
  onDepartment?: (value: string) => void;
  department?: string;
  onCreated?: (person: StaffMember) => void;
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
  const canvasRef = useRef<HTMLElement>(null);
  const [flow, setFlow] = useState<ReactFlowInstance<ChartNode> | null>(null);
  const [viewportReady, setViewportReady] = useState(false);
  const previousScene = useRef("");
  const cameraGeneration = useRef(0);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setCanvasSize((old) =>
        old.width === width && old.height === height ? old : { width, height },
      );
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (!expanded) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const exit = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !document.querySelector("dialog[open]"))
        setExpanded(false);
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
  const [creating, setCreating] = useState<{
    anchor: string;
    outgoing: boolean;
    kind: LinkKind;
    department: string;
    point: Point;
  } | null>(null);
  const reconnecting = useRef<Edge | null>(null);
  const connectionStart = useRef<Point | null>(null);
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
  const positions = useMemo(() => {
    const placed = new Map(scene.positions);
    for (const p of arranged) {
      const point = current.positions[layout]?.[p.id];
      if (point) placed.set(p.id, point);
    }
    return placed;
  }, [scene.positions, arranged, current.positions, layout]);
  // Department panels follow the actual card positions, not the reporting tree.
  // Editing a link therefore cannot move either the employee or their panel.
  const frames = useMemo(() => {
    if (
      layout !== "teams" ||
      !Object.keys(current.positions[layout] || {}).length
    )
      return scene.groups;
    return [...new Set(arranged.map((p) => p.department || "—"))]
      .filter((label) => label.toLowerCase() !== "administration")
      .map((label) => {
        const points = arranged
          .filter((p) => (p.department || "—") === label)
          .map((p) => positions.get(p.id)!);
        const x = Math.min(...points.map((p) => p.x)) - 28;
        const y = Math.min(...points.map((p) => p.y)) - 56;
        return {
          id: "department:" + label,
          label,
          x,
          y,
          width: Math.max(...points.map((p) => p.x)) - x + 328,
          height: Math.max(...points.map((p) => p.y)) - y + 176,
        };
      });
  }, [arranged, positions, scene.groups, current.positions, layout]);
  const geometry = reference(layout)
    ? referenceGeometry(layout)
    : { width: 246, height: editing ? 140 : 112 };
  // The classic layouts retain their regular cell spacing when the edit footer is visible.
  const targetNodes = useMemo<ChartNode[]>(
    () => [
      ...frames.map((frame) => ({
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
      frames,
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
  useLayoutEffect(() => {
    if (animation.current) cancelAnimationFrame(animation.current);
    if (dragging.current) return;
    const reduced = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const from = new Map(nodesRef.current.map((n) => [n.id, n.position]));
    const start = performance.now();
    const oldIds = nodesRef.current
      .map((n) => n.id)
      .sort()
      .join();
    const newIds = targetNodes
      .map((n) => n.id)
      .sort()
      .join();
    // Filtering updates the mounted canvas in one paint. Only reorders of the
    // same cards interpolate their positions; filters use the camera transition.
    if (reduced || oldIds !== newIds || !nodesRef.current.length) {
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
          reconnectable: !indirect,
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
          reconnectable: true,
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
  function beginEdit() {
    if (!config.data || busy) return;
    const next = chartDraft(all, config.data);
    const ordered = orderedStaff(all, next.orders[layout]);
    const roots = reportingParents(ordered, ordered);
    const fallback = reference(layout)
      ? referenceScene(ordered, roots, layout).positions
      : staffPositions(ordered, roots, layout);
    next.positions[layout] = {
      ...Object.fromEntries(fallback),
      ...next.positions[layout],
      ...Object.fromEntries(
        nodesRef.current
          .filter((n) => n.type === "person")
          .map((n) => [n.id, { ...n.position }]),
      ),
    };
    initial.current = {
      staff: all.map((p) => ({ ...p })),
      config: config.data,
      draft: next,
    };
    setDraft(next);
    setPast([]);
    setFuture([]);
    setSelected(null);
    setError("");
    setEditing(true);
    onEditStart?.();
  }
  function arrange() {
    if (!editing || busy) return;
    commit(arrangeCards(current, all, visibleIds, layout, geometry.height));
    setAlignment((v) => v + 1);
  }
  function cancel() {
    setEditing(false);
    initial.current = null;
    setDraft(null);
    setPast([]);
    setFuture([]);
    setSelected(null);
    setError("");
    void client.invalidateQueries({ queryKey: ["hr-staff"] });
    void config.refetch();
  }
  async function save(next = current, newStaff: NewStaff[] = []) {
    if (!editing || !initial.current || (!dirty && !newStaff.length) || busy)
      return;
    setBusy(true);
    setError("");
    try {
      const result = await request<
        StaffChartConfig & { created_staff?: StaffMember[] }
      >("/hr/staff/chart", {
        method: "PUT",
        body: JSON.stringify({
          version: initial.current.config.version,
          changes: chartChanges(next, initial.current.staff),
          extra_edges: next.extra_edges,
          orders: next.orders,
          positions: next.positions,
          ...(newStaff.length ? { new_staff: newStaff } : {}),
        }),
      });
      await Promise.all([
        client.invalidateQueries({ queryKey: ["hr-staff"] }),
        client.invalidateQueries({ queryKey: ["hr-staff-chart"] }),
      ]);
      initial.current = null;
      setEditing(false);
      setDraft(null);
      setPast([]);
      setFuture([]);
      setSelected(null);
      setCreating(null);
      if (result.created_staff?.[0]) onCreated?.(result.created_staff[0]);
      notify(
        newStaff.length
          ? L("Employee and chart saved", "Сотрудник и схема сохранены")
          : L("Organization chart saved", "Схема сохранена"),
      );
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 409
          ? L(
              "The saved data has changed. Your draft is preserved. Cancel the draft to load the current version.",
              "Сохранённые данные изменились. Черновик оставлен на экране. Отмените его, чтобы загрузить актуальную версию.",
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
    (connection: Connection | Edge) => {
      const edge = reconnecting.current;
      const next = edge
        ? removeConnection(
            current,
            edge.source,
            edge.target,
            edge.data?.kind as LinkKind,
          )
        : current;
      return (
        editing &&
        !busy &&
        !!connection.source &&
        !!connection.target &&
        canConnect(
          next,
          connection.source,
          connection.target,
          edge ? (edge.data?.kind as LinkKind) : kind,
        )
      );
    },
    [current, kind, editing, busy],
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
    (changes: NodeChange<ChartNode>[]) => {
      setNodes((ns) => applyNodeChanges(changes, ns));
      // React Flow emits completed position changes for keyboard movement too.
      // Mouse drags are committed once in onNodeDragStop instead.
      if (editing && !busy && !dragging.current) {
        let next = current;
        for (const change of changes) {
          if (
            change.type === "position" &&
            change.dragging === false &&
            change.position
          )
            next = moveCard(next, layout, change.id, change.position);
        }
        if (next !== current) commit(next);
      }
    },
    [editing, busy, current, layout, commit],
  );
  const selectedEdge = edgeData.find((e) => e.id === selected);
  const personIds = arranged
    .map((p) => p.id)
    .sort()
    .join();
  const sceneKey = `${layout}:${personIds}:${expanded}:${editing}:${canvasSize.width}:${canvasSize.height}`;
  useLayoutEffect(() => {
    if (!flow || !targetNodes.length || previousScene.current === sceneKey)
      return;
    const initialFit = !previousScene.current;
    previousScene.current = sceneKey;
    const rect = canvasRef.current?.getBoundingClientRect();
    const height = rect?.height || 600;
    const width = rect?.width || 1100;
    const reduced = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    let camera;
    if (people.length <= 12) {
      const minX = Math.min(...targetNodes.map((n) => n.position.x));
      const minY = Math.min(...targetNodes.map((n) => n.position.y));
      const maxX = Math.max(
        ...targetNodes.map(
          (n) => n.position.x + Number(n.style?.width || geometry.width),
        ),
      );
      const maxY = Math.max(
        ...targetNodes.map(
          (n) => n.position.y + Number(n.style?.height || geometry.height),
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
      camera = {
        x: left + (availableW - (maxX - minX) * zoom) / 2 - minX * zoom,
        y: top + (availableH - (maxY - minY) * zoom) / 2 - minY * zoom,
        zoom,
      };
    } else {
      const roots = arranged.filter((p) => !parents.get(p.id));
      const points = roots
        .map((p) => positions.get(p.id))
        .filter((p): p is Point => !!p);
      if (!points.length) points.push(targetNodes[0].position);
      const left = Math.min(...points.map((p) => p.x));
      const right = Math.max(...points.map((p) => p.x)) + geometry.width;
      const zoom = Math.min(
        0.8,
        Math.max(0.06, (width - 260) / (right - left)),
      );
      camera = {
        x: 210 + (width - 250) / 2 - ((left + right) / 2) * zoom,
        y: 150 - Math.min(...points.map((p) => p.y)) * zoom,
        zoom,
      };
    }
    const generation = ++cameraGeneration.current;
    void flow
      .setViewport(camera, { duration: initialFit || reduced ? 0 : 240 })
      .then(() => {
        if (mounted.current && generation === cameraGeneration.current)
          setViewportReady(true);
      });
  }, [
    flow,
    sceneKey,
    targetNodes,
    people.length,
    arranged,
    parents,
    positions,
    geometry.width,
  ]);
  function beginConnection(event: MouseEvent | TouchEvent) {
    const point = "changedTouches" in event ? event.changedTouches[0] : event;
    connectionStart.current = { x: point.clientX, y: point.clientY };
    onEditStart?.();
  }
  function finishConnection(
    event: Parameters<OnConnectEnd>[0],
    state: Parameters<OnConnectEnd>[1],
  ) {
    if (!editing || busy || creating || reconnecting.current) return;
    const point = "changedTouches" in event ? event.changedTouches[0] : event;
    const start = connectionStart.current;
    connectionStart.current = null;
    if (
      !start ||
      Math.hypot(point.clientX - start.x, point.clientY - start.y) <= 18
    )
      return;
    if (state.toNode && state.toNode.type !== "department" && !state.isValid) {
      setError(
        L(
          "This reporting link would form a cycle or duplicate a connection. Choose Additional for cross-team links.",
          "Такая связь создаёт цикл подчинения или уже существует. Для связей между коллегами выберите «Доп. связь».",
        ),
      );
      return;
    }
    const target = event.target instanceof Element ? event.target : null;
    if (
      !state.isValid &&
      state.fromNode?.type === "person" &&
      (!state.toNode || state.toNode.type === "department") &&
      target?.closest(".react-flow__pane, .react-flow__node-department")
    ) {
      setError("");
      setCreating({
        point: flow?.screenToFlowPosition({
          x: point.clientX,
          y: point.clientY,
        }) || { x: 0, y: 0 },
        anchor: state.fromNode.id,
        outgoing: state.fromHandle?.type === "source",
        kind,
        department:
          state.toNode?.type === "department"
            ? String(state.toNode.data.label)
            : department ||
              all.find((p) => p.id === state.fromNode?.id)?.department ||
              "",
      });
    }
  }
  return (
    <div
      className={`staff-graph-shell ${expanded ? "staff-graph-expanded" : ""}`}
    >
      {config.error && (
        <ErrorNotice retry={() => void config.refetch()}>
          {L(
            "Chart settings could not be loaded. Try again.",
            "Не удалось загрузить настройки схемы. Попробуйте ещё раз.",
          )}
        </ErrorNotice>
      )}
      {error && <ErrorNotice>{error}</ErrorNotice>}
      {layout === "teams" && !editing && (
        <StaffHierarchy
          people={arranged}
          all={effectiveAll}
          ru={ru}
          open={open}
          onEdit={beginEdit}
          canEdit={!!config.data && !busy}
          expanded={expanded}
          onExpand={() => setExpanded((value) => !value)}
        />
      )}
      <section
        hidden={layout === "teams" && !editing}
        ref={canvasRef}
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
          {editing
            ? L("Editing chart", "Редактирование схемы")
            : L("Team structure", "Структура команды")}
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
            {departments.map((d) => (
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
          nodes={nodes}
          edges={edgeData}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onNodesChange={onChanges}
          nodesDraggable={editing && !busy}
          nodesConnectable={editing && !busy}
          edgesReconnectable={editing && !busy}
          elementsSelectable={editing}
          deleteKeyCode={null}
          onInit={setFlow}
          style={{
            visibility: viewportReady || !people.length ? "visible" : "hidden",
          }}
          minZoom={0.06}
          maxZoom={1.5}
          preventScrolling={false}
          zoomOnScroll={false}
          zoomOnDoubleClick={false}
          proOptions={{ hideAttribution: true }}
          snapToGrid
          snapGrid={[20, 20]}
          onNodeClick={(event, node) => {
            if (
              event.target instanceof Element &&
              event.target.closest(".react-flow__handle")
            )
              return;
            setSelected(null);
            if (!editing && !busy && node.type === "person")
              open(node.data.person);
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
            if (editing && !busy && connection.source && connection.target)
              commit(
                connectDraft(
                  current,
                  connection.source,
                  connection.target,
                  kind,
                ),
              );
          }}
          onConnectStart={beginConnection}
          onConnectEnd={finishConnection}
          onReconnectStart={(_, edge) => {
            reconnecting.current = edge;
          }}
          onReconnect={(edge, connection) => {
            if (editing && !busy && connection.source && connection.target) {
              const next = reconnectDraft(
                current,
                edge.source,
                edge.target,
                connection.source,
                connection.target,
                edge.data?.kind as LinkKind,
              );
              if (next === current)
                setError(
                  L(
                    "This connection is invalid. The original connection was kept.",
                    "Недопустимая связь. Исходная связь сохранена.",
                  ),
                );
              else commit(next);
            }
          }}
          onReconnectEnd={() => {
            reconnecting.current = null;
            connectionStart.current = null;
          }}
          onNodeDragStart={() => {
            dragging.current = true;
            onEditStart?.();
            if (animation.current) cancelAnimationFrame(animation.current);
            setSelected(null);
          }}
          onNodeDragStop={(_, node) => {
            dragging.current = false;
            if (editing && !busy)
              commit(moveCard(current, layout, node.id, node.position));
          }}
        >
          <Panel position="bottom-right" className="staff-canvas-fullscreen">
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
          </Panel>
          <Panel
            position="bottom-center"
            className="staff-chart-dock"
            aria-label={L("Chart actions", "Действия со схемой")}
          >
            {!editing ? (
              <Button
                disabled={!config.data || !!config.error}
                onClick={beginEdit}
                aria-label={L("Edit chart", "Редактировать схему")}
              >
                <Pencil size={16} />
                {L("Edit chart", "Редактировать")}
              </Button>
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
                  aria-label={L("Delete connection", "Удалить связь")}
                  disabled={!selectedEdge || busy}
                  onClick={deleteSelected}
                >
                  <Trash2 size={17} />
                  {selectedEdge && L("Unlink", "Отвязать")}
                </Button>
                <Button
                  variant="ghost"
                  aria-label={L("Auto arrange", "Привести в порядок")}
                  disabled={busy}
                  onClick={arrange}
                >
                  <RotateCcw size={17} />
                  {L("Auto arrange", "Привести в порядок")}
                </Button>
                {editing && (
                  <Button
                    variant="ghost"
                    disabled={busy}
                    onClick={cancel}
                    aria-label={L("Cancel", "Отмена")}
                  >
                    <X size={17} />
                    {L("Cancel", "Отмена")}
                  </Button>
                )}
                <Button
                  variant={dirty ? "primary" : "ghost"}
                  aria-label={L("Save chart", "Сохранить схему")}
                  busy={busy}
                  disabled={!dirty || !config.data}
                  onClick={() => void save()}
                >
                  <Save size={16} />
                  {L("Save", "Сохранить")}
                </Button>{" "}
              </>
            )}
          </Panel>
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
      </section>
      <ModalPresence>
        {creating && (
          <StaffCreate
            people={all}
            department={creating.department}
            manager={
              creating.kind === "reporting" && creating.outgoing
                ? creating.anchor
                : creating.outgoing
                  ? null
                  : current.managers[creating.anchor] || null
            }
            ru={ru}
            busy={busy}
            error={error}
            close={() => {
              if (!busy) {
                setCreating(null);
                setError("");
              }
            }}
            submit={async (person) => {
              const next: ChartDraft = {
                ...current,
                positions: {
                  ...current.positions,
                  [layout]: {
                    ...current.positions[layout],
                    [person.id]: creating.point,
                  },
                },
                managers: {
                  ...current.managers,
                  [person.id]: person.manager_id,
                },
              };
              let linked = next;
              if (creating.kind === "additional" || !creating.outgoing) {
                const source = creating.outgoing ? creating.anchor : person.id;
                const target = creating.outgoing ? person.id : creating.anchor;
                if (!canConnect(next, source, target, creating.kind)) {
                  setError(
                    L(
                      "This reporting link would create a cycle. Choose another manager.",
                      "Эта связь создаёт цикл подчинения. Выберите другого руководителя.",
                    ),
                  );
                  return;
                }
                linked = connectDraft(next, source, target, creating.kind);
              }
              await save(linked, [person]);
            }}
          />
        )}
      </ModalPresence>
    </div>
  );
}
