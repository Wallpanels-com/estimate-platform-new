import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Navigate, Link } from "react-router-dom";
import {
  ArrowLeft,
  Search,
  Table2,
  Network,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { canAccess } from "../lib/access";
import { useI18n } from "../lib/i18n";
import { request, errorMessage } from "../lib/api";
import {
  ModalPresence,
  Button,
  Loading,
  ErrorNotice,
  EmptyState,
} from "../components/ui";
import Select from "../components/Select";
import { pageNumbers } from "../components/HRPagination";
import CopyContact from "../components/CopyContact";
import { primaryContacts, emailContacts } from "../lib/staffProfile";
import StaffAvatar from "../components/staff/StaffAvatar";
import StaffCard from "../components/staff/StaffCard";
import StaffGraph from "../components/staff/StaffGraph";
import type { StaffMember, StaffDirectory, StaffStatus } from "../lib/staff";
import "./staff.css";

export default function Staff() {
  const { user } = useAuth();
  return canAccess(user, "hr") ? <Directory /> : <Navigate to="/hr" replace />;
}
function Directory() {
  const { language } = useI18n();
  const ru = language === "ru";
  const L = (en: string, ruText: string) => (ru ? ruText : en);
  const query = useQuery({
    queryKey: ["hr-staff"],
    queryFn: () => request<StaffDirectory>("/hr/staff"),
    refetchInterval: 10000,
  });
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StaffStatus | "">("active");
  const [department, setDepartment] = useState("");
  const [chartDirty, setChartDirty] = useState(false);
  const [view, setView] = useState<"table" | "chart">("table");
  const layout = "teams" as const;
  const [leadersOnly, setLeadersOnly] = useState(false);
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
  if (query.isLoading) return <Loading />;
  return (
    <div className="staff-page">
      <header className="page-header">
        <div>
          <Link className="staff-back" to="/hr">
            <ArrowLeft size={16} />
            {L("HR department", "HR-отдел")}
          </Link>
          <h1>{L("Staff", "Сотрудники")}</h1>
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
            <span>
              {s ? statusName(s) : L("All employees", "Все сотрудники")}
            </span>
            <span className="staff-filter-count">
              {all.filter((p) => !s || p.status === s).length}
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
                      <StaffAvatar person={p} />
                      <span>
                        <strong>{p.name}</strong>
                        <small>{p.title || "—"}</small>
                      </span>
                    </button>
                  </td>
                  <td>{p.department || "—"}</td>
                  <td className="staff-table-contact">
                    <div className="staff-table-contacts">
                      {primaryContacts(p.fields.F || "").telegram.map(
                        (value) => (
                          <CopyContact
                            key={value}
                            value={value}
                            kind="telegram"
                          />
                        ),
                      )}
                      {primaryContacts(p.fields.F || "").phones.map((value) => (
                        <CopyContact key={value} value={value} kind="phone" />
                      ))}
                      {[
                        ...new Set([
                          ...emailContacts(p.fields.K || "").email,
                          ...emailContacts(p.fields.K || "").paypal,
                        ]),
                      ].map((value) => (
                        <CopyContact key={value} value={value} kind="email" />
                      ))}
                      {!p.fields.F && !p.fields.K && "—"}
                      {primaryContacts(p.fields.F || "").other && (
                        <span>{primaryContacts(p.fields.F || "").other}</span>
                      )}
                    </div>
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
      <ModalPresence>
        {selected && query.data && (
          <StaffCard
            key={selected.id}
            person={selected}
            directory={query.data}
            close={() => setSelected(null)}
            ru={ru}
          />
        )}
      </ModalPresence>
    </div>
  );
}
