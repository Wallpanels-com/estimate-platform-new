import { useState, useDeferredValue } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams, Navigate } from "react-router-dom";
import {
  Activity,
  BriefcaseBusiness,
  Bot,
  BarChart3,
  Phone,
  ShieldCheck,
  Download,
  Search,
  AlertTriangle,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { request, download, errorMessage } from "../lib/api";
import { Button, ErrorNotice, Loading, ModalPresence } from "../components/ui";
import type {
  GhlRecord,
  Lookups,
  SalesStatus,
  Page,
  Review,
  Report,
} from "../components/sales/types";
import {
  useSalesText,
  when,
  userName,
  Pagination,
  Blank,
} from "../components/sales/shared";
import ContactPanel from "../components/sales/ContactPanel";
import ReviewCard from "../components/sales/ReviewCard";
import Numbers from "../components/sales/Numbers";
import DealTable from "../components/sales/DealTable";
import Reports from "../components/sales/Reports";
import "./sales-control.css";

export default function SalesControl() {
  const { user } = useAuth();
  return user?.sales_control_enabled ? (
    <SalesWorkspace />
  ) : (
    <Navigate to="/" replace />
  );
}
function SalesWorkspace() {
  const s = useSalesText();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "activity";
  const page = Math.max(1, Number(params.get("page")) || 1);
  const [contact, setContact] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const q = useDeferredValue(params.get("q") || "");
  const update = (key: string, value: string) =>
    setParams((old) => {
      const n = new URLSearchParams(old);
      value ? n.set(key, value) : n.delete(key);
      if (key !== "page") n.delete("page");
      if (key === "pipeline") n.delete("stage");
      return n;
    });
  const lookup = useQuery({
    queryKey: ["sales", "lookups"],
    queryFn: () => request<Lookups>("/sales/lookups"),
    refetchInterval: 60000,
  });
  const health = useQuery({
    queryKey: ["sales", "status"],
    queryFn: () => request<SalesStatus>("/sales/status"),
    refetchInterval: 10000,
  });
  const filter = new URLSearchParams();
  for (const k of [
    "pipeline",
    "stage",
    "owner",
    "status",
    "source",
    "from_date",
    "to_date",
  ]) {
    if (params.get(k)) filter.set(k, params.get(k)!);
  }
  if (q) filter.set("q", q);
  if (tab === "leads") filter.set("status", "review");
  const f = filter.toString();
  const owner = params.get("owner") || "";
  const deals = useQuery({
    queryKey: ["sales", "opportunities", f, page],
    queryFn: ({ signal }) =>
      request<Page<GhlRecord>>(`/sales/opportunities?${f}&page=${page}`, {
        signal,
      }),
    enabled: ["deals", "leads"].includes(tab),
    refetchInterval: 15000,
  });
  const activity = useQuery({
    queryKey: ["sales", "activity", q, owner, page],
    queryFn: ({ signal }) =>
      request<Page<GhlRecord>>(
        `/sales/activity?q=${encodeURIComponent(q)}&owner=${encodeURIComponent(owner)}&page=${page}`,
        { signal },
      ),
    enabled: tab === "activity",
    refetchInterval: 10000,
  });
  const numbers = useQuery({
    queryKey: ["sales", "numbers"],
    queryFn: () => request<{ items: GhlRecord[] }>("/sales/numbers"),
    enabled: tab === "numbers",
    refetchInterval: 10000,
  });
  const reviews = useQuery({
    queryKey: ["sales", "analyses", page, params.get("concerns")],
    queryFn: () =>
      request<Page<Review>>(
        `/sales/analyses?page=${page}&concerns=${params.get("concerns") === "true"}`,
      ),
    enabled: tab === "reviews",
    refetchInterval: 15000,
  });
  const reports = useQuery({
    queryKey: ["sales", "reports", f],
    queryFn: () => request<Report>(`/sales/reports?${f}`),
    enabled: tab === "reports",
    refetchInterval: 30000,
  });
  const tabs = [
    ["activity", s("Активность", "Activity"), Activity],
    ["deals", s("Все сделки", "All opportunities"), BriefcaseBusiness],
    ["reviews", s("Разборы ИИ", "AI reviews"), Bot],
    ["leads", s("Лиды на проверку", "Lead review"), AlertTriangle],
    ["reports", s("Отчёты", "Reports"), BarChart3],
    ["numbers", s("Номера", "Numbers"), Phone],
  ] as const;
  const state = health.data;
  const opportunitySync = state?.resources.find(
    (r) => r.name === "opportunities",
  );
  const initialImport = !opportunitySync?.state.completed_at;
  const latest = state?.resources.find(
    (r) =>
      r.name ===
      (tab === "numbers"
        ? "numbers"
        : tab === "deals" || tab === "reports" || tab === "leads"
          ? "opportunity_changes"
          : "recent"),
  );
  const activeQuery =
    tab === "activity"
      ? activity
      : tab === "numbers"
        ? numbers
        : tab === "reviews"
          ? reviews
          : tab === "reports"
            ? reports
            : deals;
  const dealFilters = ["deals", "leads", "reports"].includes(tab);
  async function exportFile(format: string) {
    setExporting(true);
    setExportError("");
    try {
      await download(
        `/sales/export?${f}&format=${format}`,
        `wallpanels-opportunities.${format}`,
      );
    } catch (e) {
      setExportError(errorMessage(e));
    } finally {
      setExporting(false);
    }
  }
  return (
    <section className="sales-workspace">
      <header className="sales-header">
        <div>
          <div className="sales-eyebrow">WALL PANELS / ESTIMATOR</div>
          <h1>Sales Control</h1>
          <p>
            {s(
              "Работа с клиентами, качество разговоров и состояние сделок",
              "Client activity, conversation quality and opportunity oversight",
            )}
          </p>
        </div>
        <span className="sales-owner">
          <ShieldCheck size={16} />
          {s("Только владелец · чтение GHL", "Owner only · GHL read-only")}
        </span>
      </header>
      <div className="sales-metrics">
        <article>
          <span>{s("Opportunities в базе", "Synced opportunities")}</span>
          <strong>{(state?.counts.opportunities || 0).toLocaleString()}</strong>
          <small>{s("Все доступные статусы", "All available statuses")}</small>
        </article>
        <article>
          <span>{s("Диалоги", "Conversations")}</span>
          <strong>{(state?.counts.conversations || 0).toLocaleString()}</strong>
          <small>
            {s("История загружается постепенно", "History loads progressively")}
          </small>
        </article>
        <article>
          <span>{s("Разборы Groq", "Groq reviews")}</span>
          <strong>{(state?.analyses || 0).toLocaleString()}</strong>
          <small>{s("По доступным текстам", "Based on available text")}</small>
        </article>
        <article>
          <span>{s("Номера компании", "Company numbers")}</span>
          <strong>{state?.counts.numbers || 0}</strong>
          <small>{s("Назначения из GHL", "Assignments from GHL")}</small>
        </article>
      </div>
      <div className="sales-sync-line">
        <span className={"sales-dot " + (latest?.error ? "error" : "")} />
        <span>
          {s("Последняя загрузка", "Last fetched")}:{" "}
          {when(latest?.last_success)}
        </span>
        <details>
          <summary>{s("Состояние подключения", "Connection status")}</summary>
          <div className="sales-sync-details">
            {!state?.enabled && (
              <p>
                {s(
                  "Фоновая синхронизация выключена",
                  "Background sync is disabled",
                )}
              </p>
            )}
            {state?.resources.map((r) => (
              <p key={r.name}>
                <strong>{r.name}</strong> · {when(r.last_success)}{" "}
                {r.state.total != null &&
                  ` · ${r.state.loaded ?? r.state.total} / ${r.state.total}`}{" "}
                {r.error && <span className="sales-error">{r.error}</span>}
              </p>
            ))}
            <p>
              {s("Очередь", "Queue")}:{" "}
              {Object.entries(state?.jobs || {})
                .map(([k, v]) => `${k}: ${v}`)
                .join(" · ") || "0"}
            </p>
            <p>
              {s("Автоматический анализ", "Automatic reviews")}:{" "}
              {state?.ai_daily_limit} / {s("день", "day")}
            </p>
            {state?.job_errors.map((e, i) => (
              <p key={i}>
                {e.kind}: {e.count} · {e.error}
              </p>
            ))}
          </div>
        </details>
      </div>
      {health.error && <ErrorNotice>{errorMessage(health.error)}</ErrorNotice>}
      {latest?.error && <ErrorNotice>{latest.error}</ErrorNotice>}
      {state?.enabled && initialImport && (
        <p className="sales-import-note" role="status">
          {s("Первичная загрузка сделок", "Initial opportunity import")}:{" "}
          {(state?.counts.opportunities || 0).toLocaleString()}
          {opportunitySync?.state.total != null &&
            ` / ${opportunitySync.state.total.toLocaleString()}`}
          .{" "}
          {s(
            "Отчёты и выгрузки пока содержат только загруженные записи.",
            "Reports and exports currently contain only imported records.",
          )}
        </p>
      )}
      {!!state?.concerns && (
        <div className="sales-attention" role="status">
          <AlertTriangle size={18} />
          <span>
            {s(
              "Разборы с замечаниями, которые стоит проверить",
              "Reviews with findings to check",
            )}
            : {state.concerns}
          </span>
          <button
            className="sales-text-button"
            onClick={() => setParams({ tab: "reviews", concerns: "true" })}
          >
            {s("Посмотреть", "View")}
          </button>
        </div>
      )}
      <nav
        className="sales-tabs"
        aria-label={s("Разделы Sales Control", "Sales Control sections")}
      >
        {tabs.map(([key, label, Icon]) => (
          <button
            key={key}
            aria-current={tab === key ? "page" : undefined}
            onClick={() => update("tab", key)}
          >
            <Icon size={17} />
            {label}
          </button>
        ))}
      </nav>
      {(dealFilters || tab === "activity") && (
        <div className="sales-filters">
          <label className="sales-search">
            <Search size={17} />
            <input
              aria-label={s("Поиск клиента", "Search clients")}
              placeholder={s("Клиент или сделка…", "Client or opportunity…")}
              value={params.get("q") || ""}
              onChange={(e) => update("q", e.target.value)}
            />
          </label>
          <select
            aria-label={s("Менеджер", "Manager")}
            value={owner}
            onChange={(e) => update("owner", e.target.value)}
          >
            <option value="">{s("Все менеджеры", "All managers")}</option>
            {lookup.data?.users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </select>
          {dealFilters && (
            <>
              <select
                aria-label={s("Воронка", "Pipeline")}
                value={params.get("pipeline") || ""}
                onChange={(e) => update("pipeline", e.target.value)}
              >
                <option value="">{s("Все воронки", "All pipelines")}</option>
                {lookup.data?.pipelines.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <select
                aria-label={s("Этап", "Stage")}
                value={params.get("stage") || ""}
                onChange={(e) => update("stage", e.target.value)}
              >
                <option value="">{s("Все этапы", "All stages")}</option>
                {lookup.data?.pipelines
                  .filter(
                    (p) =>
                      !params.get("pipeline") ||
                      p.id === params.get("pipeline"),
                  )
                  .flatMap((p) => p.stages)
                  .map((st) => (
                    <option key={st.id} value={st.id}>
                      {st.name}
                    </option>
                  ))}
              </select>
              {tab !== "leads" && (
                <select
                  aria-label={s("Статус", "Status")}
                  value={params.get("status") || ""}
                  onChange={(e) => update("status", e.target.value)}
                >
                  <option value="">{s("Все статусы", "All statuses")}</option>
                  {["open", "won", "lost", "abandoned"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              )}
              <input
                aria-label={s("Источник", "Source")}
                placeholder={s(
                  "Источник: точное значение",
                  "Source: exact value",
                )}
                value={params.get("source") || ""}
                onChange={(e) => update("source", e.target.value)}
              />
              <label>
                {s("Создано с", "Created from")}
                <input
                  type="date"
                  value={params.get("from_date") || ""}
                  onChange={(e) => update("from_date", e.target.value)}
                />
              </label>
              <label>
                {s("По", "To")}
                <input
                  type="date"
                  value={params.get("to_date") || ""}
                  onChange={(e) => update("to_date", e.target.value)}
                />
              </label>
              <div className="sales-exports">
                <Button
                  variant="secondary"
                  disabled={exporting}
                  onClick={() => exportFile("xlsx")}
                >
                  <Download size={16} />
                  XLSX
                </Button>
                <Button
                  variant="secondary"
                  disabled={exporting}
                  onClick={() => exportFile("csv")}
                >
                  CSV
                </Button>
              </div>
            </>
          )}
        </div>
      )}
      {exportError && <ErrorNotice>{exportError}</ErrorNotice>}
      {tab === "leads" && (
        <p className="sales-muted">
          {s(
            "Сделки со статусом lost / abandoned. Откройте клиента, чтобы увидеть объяснения сейлза в жёлтых комментариях и разбор Groq. Статус сделки сам по себе не доказывает, что лид некачественный.",
            "Opportunities marked lost / abandoned. Open a client to read the sales explanation in internal comments and the Groq review. A lost deal does not by itself prove a poor-quality lead.",
          )}
        </p>
      )}
      {activeQuery.isLoading ? (
        <Loading />
      ) : activeQuery.error ? (
        <ErrorNotice>{errorMessage(activeQuery.error)}</ErrorNotice>
      ) : (
        <>
          {tab === "activity" && activity.data && (
            <>
              {!activity.data.items.length ? (
                <Blank>
                  {s(
                    "Ожидаем первую загрузку диалогов",
                    "Waiting for the first conversation sync",
                  )}
                </Blank>
              ) : (
                <div className="sales-activity-grid">
                  {activity.data.items.map((c) => (
                    <button
                      className="sales-activity-card"
                      key={c._id}
                      onClick={() => c.contactId && setContact(c.contactId)}
                    >
                      <div className="sales-row">
                        <span className="sales-avatar">
                          {(c.contactName || c.fullName || "?").slice(0, 1)}
                        </span>
                        <time>{when(c.lastMessageDate)}</time>
                      </div>
                      <h2>{c.contactName || c.fullName || c.contactId}</h2>
                      <p className="sales-preview">
                        {(c.lastMessageBody || "").replace(/<[^>]+>/g, " ") ||
                          s(
                            "Последнее событие без текста",
                            "Last event has no text",
                          )}
                      </p>
                      <footer>
                        <span>{userName(lookup.data, c.assignedTo)}</span>
                        <span>
                          {c.lastMessageType?.replace("TYPE_", "") || "—"}
                        </span>
                      </footer>
                    </button>
                  ))}
                </div>
              )}
              <Pagination
                {...activity.data}
                onPage={(n) => update("page", String(n))}
              />
            </>
          )}
          {["deals", "leads"].includes(tab) && deals.data && (
            <>
              <DealTable
                items={deals.data.items}
                lookups={lookup.data}
                onContact={setContact}
                showComments={tab === "leads"}
              />
              <Pagination
                {...deals.data}
                onPage={(n) => update("page", String(n))}
              />
            </>
          )}
          {tab === "numbers" && numbers.data && (
            <Numbers items={numbers.data.items} lookups={lookup.data} />
          )}
          {tab === "reviews" && reviews.data && (
            <>
              <label className="sales-concerns-filter">
                <input
                  type="checkbox"
                  checked={params.get("concerns") === "true"}
                  onChange={(e) =>
                    update("concerns", e.target.checked ? "true" : "")
                  }
                />
                {s("Только с замечаниями", "Only reviews with concerns")}
              </label>
              <p className="sales-muted">
                {s(
                  "Анализ после разговора. Каждое замечание связано с точной цитатой. Регламент Sales Ops пока не предоставлен; замечания ИИ требуют проверки.",
                  "Post-conversation analysis. Every finding links to an exact quote. Sales Ops policy has not been provided; AI findings require review.",
                )}
              </p>
              <div className="sales-review-list">
                {reviews.data.items.length ? (
                  reviews.data.items.map((r) => (
                    <ReviewCard key={r.id} review={r} onContact={setContact} />
                  ))
                ) : (
                  <Blank>
                    {s(
                      "Разборы появятся после загрузки разговоров и обработки Groq",
                      "Reviews appear after conversations are loaded and processed by Groq",
                    )}
                  </Blank>
                )}
              </div>
              <Pagination
                {...reviews.data}
                onPage={(n) => update("page", String(n))}
              />
            </>
          )}
          {tab === "reports" && reports.data && (
            <Reports report={reports.data} lookups={lookup.data} />
          )}
        </>
      )}
      <ModalPresence>
        {contact && (
          <ContactPanel
            key={contact}
            id={contact}
            onClose={() => setContact(null)}
            lookups={lookup.data}
          />
        )}
      </ModalPresence>
    </section>
  );
}
