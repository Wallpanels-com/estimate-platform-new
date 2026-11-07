import { useCallback, useMemo, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate, Link } from "react-router-dom";
import {
  ArrowLeft,
  Search,
  Table2,
  Network,
  GitBranch,
  Orbit,
  Columns3,
  Layers3,
  LockKeyhole,
  Pencil,
  Check,
  Pause,
  UserRoundX,
  ExternalLink,
  Save,
  ChevronLeft,
  ChevronRight,
  History,
  UsersRound,
  Blocks,
  Rows3,
  Workflow,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { request, patch, errorMessage } from "../lib/api";
import {
  Button,
  Field,
  Modal,
  Loading,
  ErrorNotice,
  EmptyState,
  useNotice,
} from "../components/ui";
import Select from "../components/Select";
import { pageNumbers } from "../components/HRPagination";
import StaffGraph from "../components/staff/StaffGraph";
import type {
  StaffMember,
  StaffDirectory,
  StaffLayout,
  StaffStatus,
} from "../lib/staff";
import "./staff.css";

export default function Staff() {
  const { user } = useAuth();
  return user?.can_manage_access ? (
    <Directory />
  ) : (
    <Navigate to="/hr" replace />
  );
}
const contactPreview = (value: string | undefined) => {
  const first = (value || "").split(/\r?\n/)[0].replace(/^(\d+)\.0$/, "$1");
  return first.length > 50 ? first.slice(0, 47) + "…" : first || "—";
};
const emailPreview = (value: string | undefined) =>
  (value || "").match(/[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/i)?.[0] || "";
function Directory() {
  const { language } = useI18n();
  const ru = language === "ru";
  const L = (en: string, ruText: string) => (ru ? ruText : en);
  const query = useQuery({
    queryKey: ["hr-staff"],
    queryFn: () => request<StaffDirectory>("/hr/staff"),
  });
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StaffStatus | "">("active");
  const [department, setDepartment] = useState("");
  const [chartDirty, setChartDirty] = useState(false);
  const [view, setView] = useState<"table" | "chart">("table");
  const [layout, setLayout] = useState<StaffLayout>("tree");
  const [leadersOnly, setLeadersOnly] = useState(true);
  const [selected, setSelected] = useState<StaffMember | null>(null);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(20);
  const all = query.data?.items || [];
  const filtered = useMemo(
    () =>
      all.filter(
        (p) =>
          (!status || p.status === status) &&
          (!department || p.department === department) &&
          (!search.trim() ||
            [p.name, p.title, p.department, p.fields.F, p.fields.K]
              .join(" ")
              .toLocaleLowerCase()
              .includes(search.trim().toLocaleLowerCase())),
      ),
    [all, status, department, search],
  );
  const managerIds = useMemo(
    () => new Set(all.map((p) => p.manager_id).filter(Boolean)),
    [all],
  );
  const chartPeople =
    leadersOnly && !search.trim() && !department
      ? filtered.filter((p) => managerIds.has(p.id))
      : filtered;
  const open = useCallback((p: StaffMember) => setSelected(p), []);
  const current = Math.min(
    page,
    Math.max(1, Math.ceil(filtered.length / size)),
  );
  const last = Math.max(1, Math.ceil(filtered.length / size));
  const statusName = (s: string) =>
    s === "active"
      ? L("Active", "Работает")
      : s === "paused"
        ? L("Paused", "На паузе")
        : L("Inactive", "Не работает");
  const styles: [StaffLayout, string, string, typeof Network][] = [
    ["tree", "01", "Org tree", Network],
    ["horizontal", "02", "Flow", GitBranch],
    ["orbit", "03", "Orbit", Orbit],
    ["departments", "04", "Departments", Columns3],
    ["terraces", "05", "Terraces", Layers3],
    ["teams", "07", "Team spaces", Blocks],
    ["holi", "08", "Holi tree", Workflow],
    ["compact", "09", "Holi compact", Rows3],
  ];
  const labels: Record<StaffLayout, string> = {
    tree: L("Org tree", "Дерево"),
    horizontal: L("Flow", "Горизонталь"),
    orbit: L("Orbit", "Орбиты"),
    departments: L("Departments", "Отделы"),
    terraces: L("Terraces", "Террасы"),
    teams: L("Team spaces", "Команды"),
    holi: L("Holi tree", "Holi · Дерево"),
    compact: L("Holi compact", "Holi · Компакт"),
  };
  if (query.isLoading) return <Loading />;
  return (
    <div className="staff-page">
      <header className="page-header">
        <div>
          <Link className="staff-back" to="/hr">
            <ArrowLeft size={16} />
            {L("HR department", "HR-отдел")}
          </Link>
          <h1>
            {L("Staff", "Сотрудники")}{" "}
            <span className="staff-private">
              <LockKeyhole size={13} />
              {L("Only you", "Только вы")}
            </span>
          </h1>
        </div>
        <div
          className="staff-view-switch"
          role="group"
          aria-label={L("View", "Представление")}
        >
          <Button
            variant={view === "table" ? "primary" : "ghost"}
            aria-pressed={view === "table"}
            onClick={() => {
              if (
                !chartDirty ||
                window.confirm(
                  L(
                    "Discard the unsaved chart draft?",
                    "Закрыть схему без сохранения изменений?",
                  ),
                )
              )
                setView("table");
            }}
          >
            <Table2 size={17} />
            {L("Table", "Таблица")}
          </Button>
          <Button
            variant={view === "chart" ? "primary" : "ghost"}
            aria-pressed={view === "chart"}
            onClick={() => setView("chart")}
          >
            <Network size={17} />
            {L("Structure", "Структура")}
          </Button>
        </div>
      </header>
      {query.error && <ErrorNotice>{errorMessage(query.error)}</ErrorNotice>}
      <section
        className="staff-overview"
        aria-label={L("Staff overview", "Состав команды")}
      >
        <div className="staff-overview-title">
          <UsersRound size={23} />
          <span>
            {L("WallPanels team", "Команда WallPanels")}
            <small>
              {L("Directory & reporting lines", "Справочник и подчинённость")}
            </small>
          </span>
        </div>
        {(["", "active", "paused", "inactive"] as const).map((s) => (
          <button
            key={s}
            className={status === s ? "selected" : ""}
            onClick={() => {
              setStatus(s);
              setPage(1);
            }}
            aria-pressed={status === s}
          >
            <strong>{all.filter((p) => !s || p.status === s).length}</strong>
            <span>
              {s ? statusName(s) : L("All employees", "Все сотрудники")}
            </span>
          </button>
        ))}
      </section>
      <div className="staff-toolbar">
        <label className="staff-search">
          <Search size={18} />
          <input
            aria-label={L("Search staff", "Поиск сотрудников")}
            placeholder={L(
              "Name, position or contact…",
              "Имя, должность или контакт…",
            )}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <Select
          aria-label={L("Department", "Отдел")}
          value={department}
          onChange={(e) => {
            setDepartment(e.target.value);
            setPage(1);
          }}
        >
          <option value="">{L("All departments", "Все отделы")}</option>
          {[...new Set(all.map((p) => p.department))].sort().map((d) => (
            <option key={d}>{d}</option>
          ))}
        </Select>
        <span className="staff-result-count" aria-live="polite">
          {filtered.length} {L("people", "сотрудников")}
        </span>
      </div>
      {view === "chart" && (
        <>
          <div
            className="staff-styles"
            role="group"
            aria-label={L("Chart style", "Стиль структуры")}
          >
            {styles.map(([key, num, , Icon]) => (
              <button
                key={key}
                className={`staff-style-option staff-style-${key} ${layout === key ? "selected" : ""}`}
                onClick={() => {
                  setLayout(key);
                  if (key === "teams") setLeadersOnly(false);
                }}
                aria-pressed={layout === key}
              >
                <Icon size={25} />
                <span>
                  <small>{num}</small>
                  <strong>{labels[key]}</strong>
                </span>
                {layout === key && <Check size={16} />}
              </button>
            ))}
          </div>
          <div className="staff-chart-scope">
            <button
              aria-pressed={!leadersOnly}
              onClick={() => setLeadersOnly(false)}
            >
              {L("Entire team", "Вся команда")}
            </button>
            <button
              aria-pressed={leadersOnly}
              onClick={() => setLeadersOnly(true)}
            >
              {L("Managers", "Руководители")}
            </button>
          </div>
          <p className="staff-structure-note">
            {L(
              "Initial structure: Igor Kravchenko → administration → department leads → team. Change a manager in the employee card. Dotted lines skip managers excluded by the filter.",
              "Начальная схема: Igor Kravchenko → администрация → руководители отделов → команда. Руководителя можно изменить в карточке. Пунктир пропускает руководителей, скрытых фильтром.",
            )}
          </p>
        </>
      )}
      {!query.error && !all.length ? (
        <EmptyState
          title={L("No employees yet", "Сотрудники ещё не загружены")}
        >
          {L(
            "Import the Main worksheet to get started.",
            "Загрузите лист Main для начала работы.",
          )}
        </EmptyState>
      ) : !filtered.length && view !== "chart" ? (
        <EmptyState title={L("No matching employees", "Сотрудники не найдены")}>
          {L("Try another search or filter.", "Измените поиск или фильтр.")}
        </EmptyState>
      ) : view === "chart" ? (
        <StaffGraph
          people={chartPeople}
          all={all}
          layout={layout}
          open={open}
          ru={ru}
          onDirtyChange={setChartDirty}
          onEditStart={() => setLeadersOnly(false)}
          department={department}
          onDepartment={(value) => {
            setDepartment(value);
            setLeadersOnly(false);
          }}
        />
      ) : (
        <section className="staff-table-wrap">
          <table className="staff-table">
            <thead>
              <tr>
                <th>{L("Employee", "Сотрудник")}</th>
                <th>{L("Department", "Отдел")}</th>
                <th>{L("Contact", "Контакт")}</th>
                <th>{L("Status", "Статус")}</th>
                <th>{L("Manager", "Руководитель")}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice((current - 1) * size, current * size).map((p) => (
                <tr key={p.id}>
                  <td>
                    <button
                      className="staff-name-button"
                      onClick={() => open(p)}
                    >
                      <span className="staff-avatar">
                        {p.name
                          .split(/\s+/)
                          .slice(0, 2)
                          .map((n) => n[0])
                          .join("")}
                      </span>
                      <span>
                        <strong>{p.name}</strong>
                        <small>{p.title || "—"}</small>
                      </span>
                    </button>
                  </td>
                  <td>{p.department || "—"}</td>
                  <td className="staff-table-contact">
                    <span>{contactPreview(p.fields.F)}</span>
                    <small>{emailPreview(p.fields.K)}</small>
                  </td>
                  <td>
                    <span className={`staff-status staff-status-${p.status}`}>
                      {statusName(p.status)}
                    </span>
                  </td>
                  <td>{all.find((m) => m.id === p.manager_id)?.name || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <footer className="staff-pagination">
            <span>
              {filtered.length ? (current - 1) * size + 1 : 0}–
              {Math.min(current * size, filtered.length)} / {filtered.length}
            </span>
            <Select
              aria-label={L("Employees per page", "Сотрудников на странице")}
              value={size}
              onChange={(e) => {
                setSize(Number(e.target.value));
                setPage(1);
              }}
            >
              {[20, 50, 100].map((n) => (
                <option key={n} value={n}>
                  {n} {L("per page", "на странице")}
                </option>
              ))}
            </Select>
            <nav aria-label={L("Staff pages", "Страницы сотрудников")}>
              <Button
                aria-label={L("Previous page", "Предыдущая страница")}
                disabled={current === 1}
                onClick={() => setPage(current - 1)}
              >
                <ChevronLeft size={16} />
              </Button>
              {pageNumbers(current, last).map((n) =>
                typeof n === "number" ? (
                  <Button
                    key={n}
                    variant={n === current ? "primary" : "ghost"}
                    aria-current={n === current ? "page" : undefined}
                    onClick={() => setPage(n)}
                  >
                    {n}
                  </Button>
                ) : (
                  <span key={n}>…</span>
                ),
              )}
              <Button
                aria-label={L("Next page", "Следующая страница")}
                disabled={current === last}
                onClick={() => setPage(current + 1)}
              >
                <ChevronRight size={16} />
              </Button>
            </nav>
          </footer>
        </section>
      )}
      {selected && query.data && (
        <StaffCard
          key={selected.id}
          person={selected}
          directory={query.data}
          close={() => setSelected(null)}
          drawer={view === "chart" && layout === "teams"}
          ru={ru}
        />
      )}
    </div>
  );
}
function StaffCard({
  person,
  directory,
  close,
  ru,
  drawer = false,
}: {
  person: StaffMember;
  directory: StaffDirectory;
  close: () => void;
  ru: boolean;
  drawer?: boolean;
}) {
  const L = (en: string, ruText: string) => (ru ? ruText : en);
  const client = useQueryClient();
  const notify = useNotice();
  const [form, setForm] = useState(person);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const history = useQuery({
    queryKey: ["staff-history", person.id],
    queryFn: () =>
      request<
        {
          id: string;
          actor_name: string;
          created_at: string;
          action: string;
          fields: string[];
        }[]
      >(`/hr/staff/${person.id}/history`),
    enabled: showHistory,
  });
  const dirty = JSON.stringify(form) !== JSON.stringify(person);
  function dismiss() {
    if (
      !busy &&
      (!dirty ||
        window.confirm(
          L("Discard unsaved changes?", "Закрыть без сохранения изменений?"),
        ))
    )
      close();
  }
  const field = (key: string, value: string) =>
    setForm((f) => ({ ...f, fields: { ...f.fields, [key]: value } }));
  function label(key: string) {
    return (
      directory.columns[key]?.[ru ? 1 : 0] ||
      `${L("Source column", "Столбец")} ${key}`
    );
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await patch(`/hr/staff/${person.id}`, {
        version: person.version,
        name: form.name,
        title: form.title,
        department: form.department,
        status: form.status,
        manager_id: form.manager_id,
        fields: form.fields,
        links: form.links,
      });
      await client.invalidateQueries({ queryKey: ["hr-staff"] });
      notify(L("Employee saved", "Сотрудник сохранён"));
      close();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  const groups: [string, string, string[]][] = [
    ["Contacts", "Контакты", ["F", "K", "H"]],
    ["Employment", "Работа", ["C", "D", "I", "J"]],
    ["Personal information", "Личные сведения", ["L"]],
    [
      "Documents & additional information",
      "Документы и дополнительные сведения",
      [
        "M",
        "N",
        "O",
        "P",
        ...Object.keys(form.fields).filter(
          (k) => !"ABCDEFGHIJKLMNOP".includes(k),
        ),
      ],
    ],
  ];
  const nameInput = (key: "name" | "title" | "department", caption: string) => (
    <Field label={caption}>
      {editing ? (
        <input
          value={form[key]}
          required={key === "name"}
          maxLength={key === "department" ? 160 : 240}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
        />
      ) : (
        <div className="staff-value">{form[key] || "—"}</div>
      )}
    </Field>
  );
  return (
    <Modal
      title={person.name}
      onClose={dismiss}
      wide
      className={`staff-card ${drawer ? "staff-card-drawer" : ""}`}
    >
      <form onSubmit={save}>
        <div className="modal-body">
          <div className="staff-card-toolbar">
            <span className="staff-source">
              Main · {L("row", "строка")} {person.source_row}
            </span>
            <Button
              variant="ghost"
              onClick={() => setShowHistory((v) => !v)}
              aria-expanded={showHistory}
            >
              <History size={16} />
              {L("History", "История")}
            </Button>
            {!editing && (
              <Button onClick={() => setEditing(true)}>
                <Pencil size={16} />
                {L("Edit", "Редактировать")}
              </Button>
            )}
          </div>
          {error && <ErrorNotice>{error}</ErrorNotice>}
          <div className="form-grid">
            {nameInput("name", L("Name", "Имя"))}
            {nameInput("title", L("Position", "Должность"))}
            {nameInput("department", L("Department", "Отдел"))}
            <Field label={L("Manager", "Руководитель")}>
              {editing ? (
                <Select
                  value={form.manager_id || ""}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      manager_id: e.target.value || null,
                    }))
                  }
                >
                  <option value="">
                    {L("No manager", "Без руководителя")}
                  </option>
                  {directory.items
                    .filter((p) => p.id !== person.id)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} · {p.title}
                      </option>
                    ))}
                </Select>
              ) : (
                <div className="staff-value">
                  {directory.items.find((p) => p.id === form.manager_id)
                    ?.name || "—"}
                </div>
              )}
            </Field>
          </div>
          <div
            className="staff-card-status"
            role="group"
            aria-label={L("Employment status", "Статус сотрудника")}
          >
            {(
              [
                ["active", Check, "Active", "Работает"],
                ["paused", Pause, "Paused", "На паузе"],
                ["inactive", UserRoundX, "Inactive", "Не работает"],
              ] as const
            ).map(([s, Icon, en, r]) => (
              <Button
                key={s}
                variant={form.status === s ? "primary" : "ghost"}
                disabled={busy}
                aria-pressed={form.status === s}
                onClick={() => {
                  setEditing(true);
                  setForm((f) => ({ ...f, status: s }));
                }}
              >
                <Icon size={16} />
                {L(en, r)}
              </Button>
            ))}
          </div>
          {groups.map(([en, r, keys]) => (
            <section className="staff-card-section" key={en}>
              <h3>{L(en, r)}</h3>
              <div className="form-grid">
                {keys.map((k) => (
                  <Field
                    key={k}
                    label={label(k)}
                    className={k >= "M" ? "span-all" : undefined}
                  >
                    {editing ? (
                      <div className="staff-edit-field">
                        {k >= "M" ? (
                          <textarea
                            rows={3}
                            value={form.fields[k] || ""}
                            maxLength={20000}
                            onChange={(e) => field(k, e.target.value)}
                          />
                        ) : (
                          <input
                            value={form.fields[k] || ""}
                            maxLength={20000}
                            onChange={(e) => field(k, e.target.value)}
                          />
                        )}
                        {(form.links[k] || k === "M") && (
                          <input
                            aria-label={`${label(k)} URL`}
                            type="url"
                            placeholder="https://"
                            value={form.links[k] || ""}
                            onChange={(e) =>
                              setForm((f) => ({
                                ...f,
                                links: e.target.value
                                  ? { ...f.links, [k]: e.target.value }
                                  : Object.fromEntries(
                                      Object.entries(f.links).filter(
                                        ([key]) => key !== k,
                                      ),
                                    ),
                              }))
                            }
                          />
                        )}
                      </div>
                    ) : (
                      <div className="staff-value">
                        {form.fields[k] || "—"}
                        {form.links[k] &&
                          /^(https?:\/\/|mailto:)/i.test(form.links[k]) && (
                            <a
                              href={form.links[k]}
                              target="_blank"
                              rel="noreferrer"
                              className="staff-document"
                            >
                              <ExternalLink size={14} />
                              {L("Open link", "Открыть ссылку")}
                            </a>
                          )}
                      </div>
                    )}
                  </Field>
                ))}
              </div>
            </section>
          ))}
          {showHistory && (
            <section className="staff-card-section">
              <h3>{L("Change history", "История изменений")}</h3>
              {history.isLoading ? (
                <Loading />
              ) : history.error ? (
                <ErrorNotice>{errorMessage(history.error)}</ErrorNotice>
              ) : (
                <ul className="staff-history">
                  {history.data?.map((h) => (
                    <li key={h.id}>
                      <strong>{h.actor_name}</strong>
                      <span>
                        {new Date(h.created_at).toLocaleString(
                          ru ? "ru-RU" : "en-US",
                        )}
                      </span>
                      <small>
                        {h.action === "create"
                          ? L("Employee imported", "Сотрудник импортирован")
                          : L("Employee updated", "Данные обновлены")}
                      </small>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
          <p className="staff-save-meta">
            {L("Last edited by", "Последнее изменение")}:{" "}
            {person.updated_by || "—"} ·{" "}
            {new Date(person.updated_at).toLocaleDateString(
              ru ? "ru-RU" : "en-US",
            )}
          </p>
        </div>
        <footer className="modal-footer">
          <Button onClick={dismiss} disabled={busy}>
            {L("Close", "Закрыть")}
          </Button>
          {editing && (
            <Button
              type="submit"
              variant="primary"
              busy={busy}
              disabled={!dirty}
            >
              <Save size={17} />
              {L("Save changes", "Сохранить изменения")}
            </Button>
          )}
        </footer>
      </form>
    </Modal>
  );
}
