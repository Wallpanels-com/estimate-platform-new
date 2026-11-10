import { useMemo } from "react";
import { ArrowUpRight, Maximize2, Minimize2, Pencil } from "lucide-react";
import type { StaffMember } from "../../lib/staff";
import { staffHierarchy } from "../../lib/staffHierarchy";
import { Button } from "../ui";
import StaffAvatar from "./StaffAvatar";

export default function StaffHierarchy({
  people,
  all,
  ru,
  open,
  onEdit,
  canEdit,
  expanded,
  onExpand,
}: {
  people: StaffMember[];
  all: StaffMember[];
  ru: boolean;
  open: (person: StaffMember) => void;
  onEdit: () => void;
  canEdit: boolean;
  expanded: boolean;
  onExpand: () => void;
}) {
  const { founders, departments } = useMemo(
    () => staffHierarchy(people),
    [people],
  );
  const everyone = useMemo(() => new Map(all.map((p) => [p.id, p])), [all]);
  const L = (en: string, russian: string) => (ru ? russian : en);
  function personCard(person: StaffMember, lead = false) {
    return (
      <button
        type="button"
        className={`staff-hierarchy-person ${lead ? "is-lead" : ""}`}
        onClick={() => open(person)}
        aria-label={`${L("Open employee", "Открыть карточку")}: ${person.name}`}
      >
        <StaffAvatar person={person} />
        <span className="staff-hierarchy-identity">
          <strong>{person.name}</strong>
          {person.title && <span>{person.title}</span>}
          {person.status !== "active" && (
            <small>
              {person.status === "paused"
                ? L("Paused", "На паузе")
                : L("Inactive", "Не работает")}
            </small>
          )}
        </span>
        <ArrowUpRight size={14} aria-hidden="true" />
      </button>
    );
  }
  function branch(person: StaffMember, children: Map<string, StaffMember[]>) {
    const reports = children.get(person.id) || [];
    return (
      <li key={person.id}>
        {personCard(person, reports.length > 0)}
        {reports.length > 0 && (
          <ul className="staff-hierarchy-reports">
            {reports.map((p) => branch(p, children))}
          </ul>
        )}
      </li>
    );
  }
  return (
    <section
      className="staff-hierarchy"
      aria-label={L("Team structure", "Структура команды")}
    >
      <div className="staff-hierarchy-toolbar">
        <span>
          {people.length} {L("people", "сотрудников")}
          <i aria-hidden="true">·</i>
          {departments.length} {L("departments", "отделов")}
        </span>
        <div>
          <Button variant="ghost" onClick={onEdit} disabled={!canEdit}>
            <Pencil size={15} />
            {L("Edit chart", "Редактировать схему")}
          </Button>
          <Button
            variant="ghost"
            onClick={onExpand}
            aria-label={
              expanded
                ? L("Close full screen", "Закрыть полный экран")
                : L("Full screen", "На весь экран")
            }
          >
            {expanded ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
          </Button>
        </div>
      </div>
      {founders.length > 0 && (
        <div
          className={`staff-hierarchy-foundation ${departments.length ? "has-departments" : ""}`}
        >
          <header>{L("Founders", "Совладельцы")}</header>
          <div className="staff-hierarchy-founders">
            {founders.map((p) => (
              <div key={p.id}>{personCard(p, true)}</div>
            ))}
          </div>
        </div>
      )}
      {founders.length > 0 && departments.length > 0 && (
        <div className="staff-hierarchy-divider">
          <span>{L("Departments", "Отделы")}</span>
        </div>
      )}
      <div className="staff-hierarchy-grid">
        {departments.map((group) => {
          const external = [
            ...new Set(
              group.roots
                .map((p) => p.manager_id)
                .filter(
                  (id): id is string =>
                    !!id && !group.members.some((p) => p.id === id),
                ),
            ),
          ]
            .map((id) => everyone.get(id))
            .filter((p): p is StaffMember => !!p);
          return (
            <section
              className="staff-hierarchy-department"
              key={group.name}
              aria-label={group.name || L("No department", "Без отдела")}
            >
              <header>
                <h3>{group.name || L("No department", "Без отдела")}</h3>
                <span>{group.members.length}</span>
              </header>
              {external.length > 0 && (
                <div className="staff-hierarchy-managers">
                  <span>{L("Reports to", "Подчинение")}</span>
                  <div>
                    {external.map((p) => (
                      <button type="button" key={p.id} onClick={() => open(p)}>
                        {p.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <ul className="staff-hierarchy-members">
                {group.roots.map((p) => branch(p, group.children))}
              </ul>
            </section>
          );
        })}
      </div>
      {!people.length && (
        <p className="staff-hierarchy-empty">
          {L(
            "No employees match these filters. Clear a filter to continue.",
            "Нет сотрудников по выбранным фильтрам. Измените фильтр.",
          )}
        </p>
      )}
    </section>
  );
}
