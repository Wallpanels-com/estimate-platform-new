import { memo, useCallback, useMemo } from "react";
import {
  ReactFlow,
  BaseEdge,
  getSmoothStepPath,
  type EdgeProps,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  type NodeProps,
  type Node,
  type Edge,
} from "@xyflow/react";
import { ArrowUpRight, Circle } from "lucide-react";
import {
  reportingParents,
  staffPositions,
  type StaffMember,
  type StaffLayout,
} from "../../lib/staff";
import "@xyflow/react/dist/style.css";

type PersonData = {
  person: StaffMember;
  open: (p: StaffMember) => void;
  horizontal: boolean;
  ru: boolean;
  indirect: boolean;
} & Record<string, unknown>;
type PersonNode = Node<PersonData, "person">;
const Person = memo(function Person({ data }: NodeProps<PersonNode>) {
  const p = data.person;
  return (
    <div className={`staff-person staff-person-${p.status}`}>
      <Handle
        type="target"
        position={data.horizontal ? Position.Left : Position.Top}
        isConnectable={false}
      />
      <button
        type="button"
        className="staff-person-open nodrag nopan"
        onClick={(event) => {
          event.stopPropagation();
          data.open(p);
        }}
        aria-label={`${data.ru ? "Открыть карточку" : "Open employee"}: ${p.name}`}
      >
        <span className="staff-person-top">
          <span className="staff-avatar">
            {p.name
              .split(/\s+/)
              .slice(0, 2)
              .map((n) => n[0])
              .join("")}
          </span>
          <span
            className={`staff-status-dot ${p.status}`}
            aria-label={p.status}
          />
          <ArrowUpRight size={15} />
        </span>
        <strong>{p.name}</strong>
        <span className="staff-person-title">{p.title || "—"}</span>
        <span className="staff-person-dept">
          {p.department || "—"}
          {data.indirect && (
            <Circle
              size={7}
              aria-label={
                data.ru
                  ? "Промежуточный руководитель скрыт фильтром"
                  : "Intermediate manager is filtered out"
              }
            />
          )}
        </span>
      </button>
      <Handle
        type="source"
        position={data.horizontal ? Position.Right : Position.Bottom}
        isConnectable={false}
      />
    </div>
  );
});
const nodeTypes = { person: Person };
function TreeEdge(props: EdgeProps) {
  const bus = props.data?.busX as number | undefined;
  const [normal] = getSmoothStepPath(props);
  const path =
    bus === undefined
      ? normal
      : `M ${props.sourceX},${props.sourceY} V ${props.sourceY + 24} H ${bus} V ${props.targetY - 24} H ${props.targetX} V ${props.targetY}`;
  return <BaseEdge path={path} style={props.style} />;
}
const edgeTypes = { staffTree: TreeEdge };
export default function StaffGraph({
  people,
  all,
  layout,
  open,
  ru,
}: {
  people: StaffMember[];
  all: StaffMember[];
  layout: StaffLayout;
  open: (p: StaffMember) => void;
  ru: boolean;
}) {
  const parents = useMemo(() => reportingParents(people, all), [people, all]);
  const positions = useMemo(
    () => staffPositions(people, parents, layout),
    [people, parents, layout],
  );
  const horizontal = layout === "horizontal";
  const nodes = useMemo<PersonNode[]>(
    () =>
      people.map((p) => ({
        id: p.id,
        type: "person",
        position: positions.get(p.id) || { x: 0, y: 0 },
        draggable: false,
        connectable: false,
        selectable: false,
        data: {
          person: p,
          open,
          horizontal,
          ru,
          indirect: !!parents.get(p.id) && parents.get(p.id) !== p.manager_id,
        },
      })),
    [people, positions, open, horizontal, ru, parents],
  );
  const edges = useMemo<Edge[]>(
    () =>
      people.flatMap((p) => {
        const parent = parents.get(p.id);
        return parent
          ? [
              {
                id: `${parent}-${p.id}`,
                source: parent,
                target: p.id,
                type:
                  layout === "tree"
                    ? "staffTree"
                    : layout === "orbit"
                      ? "default"
                      : "smoothstep",
                data:
                  layout === "tree" &&
                  new Set(
                    people
                      .filter((child) => parents.get(child.id) === parent)
                      .map((child) => positions.get(child.id)?.y),
                  ).size > 1
                    ? {
                        busX:
                          Math.min(
                            ...people
                              .filter(
                                (child) => parents.get(child.id) === parent,
                              )
                              .map((child) => positions.get(child.id)?.x || 0),
                          ) - 30,
                      }
                    : {},
                className:
                  parent !== p.manager_id
                    ? "staff-edge-indirect"
                    : "staff-edge",
                style: { strokeWidth: 1.4 },
                selectable: false,
              },
            ]
          : [];
      }),
    [people, parents, layout, positions],
  );
  const color = useCallback(
    (node: Node) =>
      (node.data as PersonData).person.status === "active"
        ? "#5d8178"
        : "#a4a9b1",
    [],
  );
  return (
    <section
      className={`staff-canvas staff-canvas-${layout}`}
      aria-label={ru ? "Организационная структура" : "Organization chart"}
    >
      <div className="staff-canvas-caption">
        <span className="staff-live-dot" />
        {ru ? "СХЕМА КОМАНДЫ" : "TEAM STRUCTURE"}
        <span>
          {people.length} {ru ? "сотрудников" : "people"}
        </span>
      </div>
      <ReactFlow
        key={`${layout}-${people.map((p) => p.id).join()}`}
        nodes={nodes}
        edges={edges}
        onNodeClick={(_, node) => open(node.data.person)}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        edgesReconnectable={false}
        elementsSelectable={false}
        deleteKeyCode={null}
        fitView={people.length <= 12}
        onInit={(instance) => {
          if (people.length <= 12) return;
          const root = people.find((p) => !parents.get(p.id));
          const position = root && positions.get(root.id);
          if (position)
            void instance.setCenter(position.x + 123, position.y + 250, {
              zoom: 0.8,
            });
        }}
        fitViewOptions={{ padding: 0.12, maxZoom: 1 }}
        minZoom={0.08}
        maxZoom={1.5}
        preventScrolling={false}
        zoomOnScroll={false}
        zoomOnDoubleClick={false}
        attributionPosition="top-right"
      >
        <Background
          gap={24}
          size={1}
          color={layout === "orbit" ? "#324754" : "#d9dfe1"}
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
        {ru
          ? "Перемещение — перетаскиванием фона · Масштаб — кнопками + / − · Карточка — по клику"
          : "Drag the background to pan · Use + / − to zoom · Click a person for details"}
      </span>
    </section>
  );
}
