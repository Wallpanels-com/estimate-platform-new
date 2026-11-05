import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Upload,
  Pencil,
  Star,
  Search,
  MapPin,
  BriefcaseBusiness,
  Eye,
  EyeOff,
  StickyNote,
} from "lucide-react";
import { request, post, patch, errorMessage } from "../lib/api";
import { useI18n } from "../lib/i18n";
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
import HRPagination from "../components/HRPagination";
import CopyContact from "../components/CopyContact";
import CandidateAI from "../components/CandidateAI";

type Vacancy = {
  id: string;
  name: string;
  description: string;
  archived: boolean;
  updated_at: string;
  count: number;
};
type Candidate = {
  id: string;
  name: string;
  email: string;
  phone: string;
  telegram_username?: string | null;
  answers: Record<string, string>;
  source: string;
  status: string;
  priority: boolean;
  hidden: boolean;
  location: string;
  location_verified: boolean;
  notes: string;
  version: number;
  updated_by: string;
  updated_at: string;
  contact_flags: string[];
  score: number | null;
  evidence: {
    criterion: string;
    question: string;
    answer: string;
    points: number;
    maximum: number;
  }[];
};
type Results = {
  items: Candidate[];
  page: number;
  total: number;
  counts: Record<string, number>;
};
type Sheet = {
  name: string;
  columns: string[];
  count: number;
  mapping: Record<string, string>;
};
type Batch = { id: string; sheets: Sheet[] };
type ImportResult = {
  added: number;
  duplicates: number;
  invalid: number;
  test_rows: number;
  sample?: { name: string; email: string; phone: string }[];
};
const statuses: Record<string, string> = {
  new: "New candidate",
  review: "In review",
  contacted: "Contacted",
  interview: "Interview",
  offer: "Offer",
  hired: "Hired",
  rejected: "Not selected",
  archived: "Archived",
};
const friendly = (s: string) => s.replaceAll("_", " ");
const professional = (answers: Record<string, string>) =>
  Object.entries(answers).filter(
    ([k]) =>
      ![
        "id",
        "created_time",
        "lead_status",
        "Priority",
        "platform",
        "is_organic",
      ].includes(k) &&
      !k.match(/^(ad|adset|campaign|form)_/i) &&
      !k.match(/имя|адрес|номер|email|name|phone/i),
  );
export default function HR() {
  const { t, language } = useI18n();
  const client = useQueryClient();
  const notify = useNotice();
  const vacancies = useQuery({
    queryKey: ["hr-vacancies"],
    queryFn: () => request<Vacancy[]>("/hr/vacancies"),
  });
  const [selected, setSelected] = useState("");
  const [showArchive, setShowArchive] = useState(false);
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState(false);
  const [hiddenView, setHiddenView] = useState(false);
  const [notesFocus, setNotesFocus] = useState(false);
  const [pendingRows, setPendingRows] = useState<Set<string>>(new Set());
  const actionLocks = useRef(new Set<string>());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => {
    try {
      const stored = Number(localStorage.getItem("wallpanels.hr.page-size"));
      return [20, 50, 100].includes(stored) ? stored : 50;
    } catch {
      return 50;
    }
  });
  const board = useRef<HTMLElement>(null);
  function goToPage(value: number) {
    setPage(value);
    board.current?.scrollIntoView({ block: "start" });
  }
  const [edit, setEdit] = useState<Vacancy | "new" | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const visible = (vacancies.data || []).filter(
    (v) => showArchive || !v.archived,
  );
  const current = visible.find((v) => v.id === selected) || visible[0];
  const ident = current?.id;
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(q);
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [q]);
  const query = useQuery({
    queryKey: [
      "hr-candidates",
      ident,
      search,
      status,
      priority,
      page,
      pageSize,
      hiddenView,
    ],
    enabled: !!ident,
    queryFn: () =>
      request<Results>(
        `/hr/vacancies/${ident}/candidates?${new URLSearchParams({ q: search, status: status || "", priority: String(priority), page: String(page), page_size: String(pageSize), hidden: String(hiddenView) }).toString().replace("status=&", "")}`,
      ),
    refetchInterval: 20000,
    refetchOnWindowFocus: true,
  });
  useEffect(() => {
    if (query.data && query.data.page !== page) setPage(query.data.page);
  }, [query.data, page]);
  function refresh() {
    return Promise.all([
      client.invalidateQueries({ queryKey: ["hr-candidates"] }),
      client.invalidateQueries({ queryKey: ["hr-vacancies"] }),
    ]);
  }
  async function quickAction(c: Candidate, key: "priority" | "hidden") {
    if (actionLocks.current.has(c.id)) return;
    actionLocks.current.add(c.id);
    setPendingRows(new Set(actionLocks.current));
    try {
      await patch<Candidate>(`/hr/candidates/${c.id}/quick`, {
        version: c.version,
        [key]: !c[key],
      });
      await refresh();
      if (key === "hidden")
        notify(
          t(c.hidden ? "Candidate restored" : "Candidate moved to Hidden"),
        );
    } catch (e) {
      notify(t(errorMessage(e)), true);
      await refresh();
    } finally {
      actionLocks.current.delete(c.id);
      setPendingRows(new Set(actionLocks.current));
    }
  }
  async function saveVacancy(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const body = {
        name: f.get("name"),
        description: f.get("description"),
        archived: f.get("archived") === "on",
        expected_updated_at: edit !== "new" ? edit?.updated_at : undefined,
      };
      const v =
        edit === "new"
          ? await post<Vacancy>("/hr/vacancies", body)
          : await patch<Vacancy>(`/hr/vacancies/${edit?.id}`, body);
      setSelected(v.id);
      setEdit(null);
      refresh();
      void client.invalidateQueries({ queryKey: ["hr-ai"] });
      notify(t("Vacancy saved"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  const date = (v: string) =>
    new Date(v).toLocaleDateString(language === "ru" ? "ru-RU" : "en-US");
  return (
    <div className="hr-page">
      <header className="page-header">
        <div className="min-zero">
          <h1>{t("HR department")}</h1>
        </div>
        <div className="page-actions">
          <Button
            onClick={() => {
              setEdit("new");
              setError("");
            }}
          >
            <Plus size={17} />
            {t("Add vacancy")}
          </Button>
          <Button
            variant="primary"
            disabled={!current || current.archived}
            onClick={() => setImporting(true)}
          >
            <Upload size={17} />
            {t("Import Excel")}
          </Button>
        </div>
      </header>
      {vacancies.isPending ? (
        <Loading />
      ) : vacancies.isError ? (
        <ErrorNotice retry={() => void vacancies.refetch()}>
          {errorMessage(vacancies.error)}
        </ErrorNotice>
      ) : (
        <>
          <div className="hr-vacancy-bar">
            <div className="hr-tabs" role="tablist" aria-label={t("Vacancies")}>
              {visible.map((v) => (
                <button
                  key={v.id}
                  role="tab"
                  aria-selected={ident === v.id}
                  className={ident === v.id ? "active" : ""}
                  onClick={() => {
                    setSelected(v.id);
                    setPage(1);
                    setStatus("");
                    setQ("");
                  }}
                >
                  <BriefcaseBusiness size={16} />
                  <span>
                    {v.name}
                    {v.archived ? ` · ${t("Archived")}` : ""}
                  </span>
                  <small>{v.count}</small>
                </button>
              ))}
            </div>
            <label className="hr-checkbox">
              <input
                type="checkbox"
                checked={showArchive}
                onChange={(e) => setShowArchive(e.target.checked)}
              />
              {t("Show archive")}
            </label>
          </div>
          {!current ? (
            <EmptyState
              title="No vacancies yet"
              action={
                <Button onClick={() => setEdit("new")}>
                  {t("Add vacancy")}
                </Button>
              }
            >
              {t("Create a vacancy, then import its candidate workbook.")}
            </EmptyState>
          ) : (
            <section className="hr-board" ref={board}>
              <div className="hr-board-heading">
                <div className="min-zero">
                  <h2>{current.name}</h2>
                  {current.description && (
                    <p className="hr-description">{current.description}</p>
                  )}
                </div>
                <Button
                  variant="ghost"
                  aria-label={t("Edit vacancy")}
                  onClick={() => {
                    setEdit(current);
                    setError("");
                  }}
                >
                  <Pencil size={17} />
                </Button>
              </div>
              <div
                className="hr-view-tabs"
                role="group"
                aria-label={t("Candidate visibility")}
              >
                <Button
                  variant={!hiddenView ? "primary" : "ghost"}
                  aria-pressed={!hiddenView}
                  onClick={() => {
                    setHiddenView(false);
                    setPriority(false);
                    setStatus("");
                    setPage(1);
                  }}
                >
                  <Eye size={16} />
                  {t("Visible candidates")}
                </Button>
                <Button
                  variant={hiddenView ? "primary" : "ghost"}
                  aria-pressed={hiddenView}
                  onClick={() => {
                    setHiddenView(true);
                    setPriority(false);
                    setStatus("");
                    setPage(1);
                  }}
                >
                  <EyeOff size={16} />
                  {t("Hidden candidates")}
                </Button>
              </div>
              <div className="hr-toolbar">
                <div className="hr-search">
                  <Search size={17} />
                  <input
                    aria-label={t("Search candidates")}
                    placeholder={t("Search name, email or phone")}
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                  />
                </div>
                <Select
                  aria-label={t("Candidate status")}
                  value={status}
                  onChange={(e) => {
                    setStatus(e.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">{t("All active statuses")}</option>
                  {Object.entries(statuses).map(([v, l]) => (
                    <option key={v} value={v}>
                      {t(l)}
                    </option>
                  ))}
                </Select>
                <Button
                  aria-pressed={priority}
                  onClick={() => {
                    setPriority(!priority);
                    setPage(1);
                  }}
                >
                  <Star size={16} fill={priority ? "currentColor" : "none"} />
                  {t("Priority")}
                </Button>
                <div className="hr-page-size">
                  <Field label="Candidates per page">
                    <Select
                      value={pageSize}
                      onChange={(e) => {
                        const value = Number(e.target.value);
                        setPageSize(value);
                        setPage(1);
                        try {
                          localStorage.setItem(
                            "wallpanels.hr.page-size",
                            String(value),
                          );
                        } catch {
                          /* Preference is optional. */
                        }
                      }}
                    >
                      {[20, 50, 100].map((n) => (
                        <option key={n} value={n}>
                          {t("{0} / page", n)}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>
              </div>
              <p className="hr-sort-note">
                {t(
                  "HR priority first, then professional match: experience, English, US market and drawings.",
                )}
              </p>
              {query.isPending ? (
                <Loading />
              ) : query.isError ? (
                <ErrorNotice retry={() => void query.refetch()}>
                  {errorMessage(query.error)}
                </ErrorNotice>
              ) : query.data?.items.length ? (
                <>
                  <div className="hr-table-wrap">
                    <table className="hr-table">
                      <thead>
                        <tr>
                          <th>{t("Candidate")}</th>
                          <th>{t("Experience & skills")}</th>
                          <th>{t("Candidate status")}</th>
                          <th>{t("Updated")}</th>
                          <th>{t("Actions")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {query.data.items.map((c) => (
                          <tr
                            key={c.id}
                            className={c.priority ? "hr-priority" : ""}
                          >
                            <td>
                              <button
                                className="hr-name"
                                disabled={pendingRows.has(c.id)}
                                onClick={() => {
                                  setNotesFocus(false);
                                  setCandidate(c);
                                }}
                              >
                                {c.name}
                              </button>
                              <CopyContact
                                value={c.email}
                                kind="email"
                                className={
                                  c.contact_flags.includes("email_ru")
                                    ? "hr-contact-review"
                                    : ""
                                }
                              />
                              <div className="hr-phone-row">
                                <CopyContact
                                  value={c.phone}
                                  kind="phone"
                                  className={
                                    c.contact_flags.includes("phone_plus7")
                                      ? "hr-contact-review"
                                      : ""
                                  }
                                />
                              </div>
                            </td>
                            <td>
                              <div className="hr-skills">
                                <strong
                                  className={
                                    c.score !== null && c.score >= 80
                                      ? "hr-high-match"
                                      : ""
                                  }
                                >
                                  {c.score === null
                                    ? t("Not scored")
                                    : `${c.score}/100`}
                                </strong>
                                {professional(c.answers)
                                  .slice(0, 2)
                                  .map(([k, v]) => (
                                    <span key={k} title={friendly(k)}>
                                      {friendly(v)}
                                    </span>
                                  ))}
                              </div>
                            </td>
                            <td>
                              <span
                                className={`hr-status hr-status-${c.status}`}
                              >
                                {t(statuses[c.status] || c.status)}
                              </span>
                            </td>
                            <td className="hr-updated">
                              {date(c.updated_at)}
                              <small>{c.updated_by}</small>
                            </td>
                            <td className="hr-action-cell">
                              <div className="hr-row-actions">
                                <Button
                                  variant="ghost"
                                  className={
                                    c.priority ? "hr-star-selected" : ""
                                  }
                                  aria-label={t(
                                    c.priority
                                      ? "Remove candidate priority"
                                      : "Prioritize candidate",
                                  )}
                                  aria-pressed={c.priority}
                                  disabled={pendingRows.has(c.id)}
                                  onClick={() =>
                                    void quickAction(c, "priority")
                                  }
                                >
                                  <Star
                                    size={17}
                                    fill={c.priority ? "currentColor" : "none"}
                                  />
                                </Button>
                                <Button
                                  variant="ghost"
                                  aria-label={t("Candidate note")}
                                  className={c.notes ? "hr-note-present" : ""}
                                  disabled={pendingRows.has(c.id)}
                                  onClick={() => {
                                    setNotesFocus(true);
                                    setCandidate(c);
                                  }}
                                >
                                  <StickyNote size={17} />
                                </Button>
                                <Button
                                  variant="ghost"
                                  aria-label={t(
                                    c.hidden
                                      ? "Restore candidate"
                                      : "Hide candidate",
                                  )}
                                  disabled={pendingRows.has(c.id)}
                                  onClick={() => void quickAction(c, "hidden")}
                                >
                                  {c.hidden ? (
                                    <Eye size={17} />
                                  ) : (
                                    <EyeOff size={17} />
                                  )}
                                </Button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <HRPagination
                    page={query.data.page}
                    pageSize={pageSize}
                    total={query.data.total}
                    onChange={goToPage}
                  />
                </>
              ) : (
                <EmptyState
                  title={
                    hiddenView ? "No hidden candidates" : "No candidates found"
                  }
                >
                  {t(
                    hiddenView
                      ? "Hidden candidates appear here and can be restored at any time."
                      : "Import an Excel file or change your filters.",
                  )}
                </EmptyState>
              )}
            </section>
          )}
        </>
      )}
      {edit && (
        <Modal
          title={edit === "new" ? "Add vacancy" : "Edit vacancy"}
          onClose={() => {
            if (!busy) setEdit(null);
          }}
        >
          <form onSubmit={saveVacancy}>
            <div className="modal-body form-grid">
              <Field label="Vacancy name" className="span-all">
                <input
                  name="name"
                  required
                  maxLength={160}
                  defaultValue={edit === "new" ? "" : edit.name}
                />
              </Field>
              <Field label="Job requirements" className="span-all">
                <textarea
                  name="description"
                  rows={4}
                  maxLength={4000}
                  defaultValue={edit === "new" ? "" : edit.description}
                />
              </Field>
              {edit !== "new" && (
                <label className="hr-checkbox span-all">
                  <input
                    name="archived"
                    type="checkbox"
                    defaultChecked={edit.archived}
                  />
                  {t("Archive vacancy")}
                </label>
              )}
              {error && (
                <p role="alert" className="error-message span-all">
                  {error}
                </p>
              )}
            </div>
            <footer className="modal-footer">
              <Button disabled={busy} onClick={() => setEdit(null)}>
                {t("Cancel")}
              </Button>
              <Button type="submit" variant="primary" busy={busy}>
                {t("Save vacancy")}
              </Button>
            </footer>
          </form>
        </Modal>
      )}
      {candidate && (
        <CandidateCard
          initial={candidate}
          focusNotes={notesFocus}
          onClose={() => setCandidate(null)}
          onSaved={(c) => {
            setCandidate(c);
            refresh();
          }}
        />
      )}
      {importing && current && (
        <ImportDialog
          vacancy={current}
          onClose={() => setImporting(false)}
          onDone={(r) => {
            setHiddenView(false);
            setPage(1);
            refresh();
            setImporting(false);
            notify(
              t(
                "Imported: {0}. Duplicates skipped: {1}.",
                r.added,
                r.duplicates,
              ),
            );
          }}
        />
      )}
    </div>
  );
}
function CandidateCard({
  initial: c,
  focusNotes = false,
  onClose,
  onSaved,
}: {
  initial: Candidate;
  focusNotes?: boolean;
  onClose: () => void;
  onSaved: (c: Candidate) => void;
}) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [cardTab, setCardTab] = useState<"ai" | "application">(
    focusNotes ? "application" : "ai",
  );
  const notesInput = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (focusNotes) notesInput.current?.focus();
  }, [focusNotes]);
  const history = useQuery({
    queryKey: ["hr-history", c.id, c.version],
    queryFn: () =>
      request<
        {
          id: string;
          actor_name: string;
          created_at: string;
          action: string;
          fields: string[];
        }[]
      >(`/hr/candidates/${c.id}/history`),
  });
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      onSaved(
        await patch<Candidate>(`/hr/candidates/${c.id}`, {
          version: c.version,
          status: f.get("status"),
          priority: f.get("priority") === "on",
          location: c.location,
          location_verified: c.location_verified,
          notes: f.get("notes"),
          telegram_username: f.get("telegram_username") || null,
        }),
      );
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={c.name}
      wide
      className="hr-review-modal"
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <form onSubmit={save}>
        <div className="modal-body hr-candidate-body">
          <div className="hr-candidate-contact">
            <CopyContact value={c.email} kind="email" />
            <CopyContact value={c.phone} kind="phone" />
          </div>
          {c.contact_flags.length > 0 && (
            <div className="hr-contact-flags">
              <MapPin size={16} />
              <span>
                {c.contact_flags
                  .map((f) =>
                    t(
                      f === "phone_plus7"
                        ? "Phone +7 — confirm location"
                        : "Email .ru — confirm location",
                    ),
                  )
                  .join(" · ")}
                <small>
                  {t(
                    "Contact details do not establish citizenship or residence and do not affect priority.",
                  )}
                </small>
              </span>
            </div>
          )}
          <div
            className="hr-card-tabs"
            role="tablist"
            aria-label={t("Candidate card")}
          >
            <Button
              role="tab"
              aria-selected={cardTab === "ai"}
              aria-controls="hr-ai-panel"
              variant={cardTab === "ai" ? "primary" : "ghost"}
              onClick={() => setCardTab("ai")}
            >
              {t("Application review")}
            </Button>
            <Button
              role="tab"
              aria-selected={cardTab === "application"}
              aria-controls="hr-application-panel"
              variant={cardTab === "application" ? "primary" : "ghost"}
              onClick={() => setCardTab("application")}
            >
              {t("Application & notes")}
            </Button>
          </div>
          <div id="hr-ai-panel" role="tabpanel" hidden={cardTab !== "ai"}>
            <CandidateAI key={c.id} id={c.id} active={cardTab === "ai"} />
          </div>
          <div
            id="hr-application-panel"
            role="tabpanel"
            hidden={cardTab !== "application"}
          >
            <div className="form-grid">
              <Field label="Candidate status">
                <Select name="status" defaultValue={c.status}>
                  {Object.entries(statuses).map(([v, l]) => (
                    <option key={v} value={v}>
                      {t(l)}
                    </option>
                  ))}
                </Select>
              </Field>
              <label className="hr-checkbox hr-priority-control">
                <input
                  name="priority"
                  type="checkbox"
                  defaultChecked={c.priority}
                />
                <Star size={16} />
                {t("Priority candidate")}
              </label>
              <Field
                label="Telegram username"
                className="span-all hr-telegram-field"
              >
                <input
                  name="telegram_username"
                  maxLength={200}
                  defaultValue={c.telegram_username || ""}
                  placeholder={t("@username or https://t.me/username")}
                  autoComplete="off"
                />
              </Field>
              <Field label="HR notes" className="span-all">
                <textarea
                  name="notes"
                  ref={notesInput}
                  rows={3}
                  maxLength={20000}
                  defaultValue={c.notes}
                />
              </Field>
            </div>
            <section className="hr-answers">
              <h3>
                {t("Professional match")}:{" "}
                {c.score === null ? t("Not scored") : `${c.score}/100`}
              </h3>
              <p className="hr-muted">
                {t(
                  "Equal weight for available criteria: experience, English, US market and technical drawings. Self-reported answers; human review required.",
                )}
              </p>
              <dl>
                {c.evidence.map((e) => (
                  <div key={e.criterion}>
                    <dt>{friendly(e.question)}</dt>
                    <dd>
                      {friendly(e.answer) || "—"} · {e.points}/{e.maximum}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
            <section className="hr-answers">
              <h3>{t("Application answers")}</h3>
              <dl>
                {professional(c.answers).map(([k, v]) => (
                  <div key={k}>
                    <dt>{friendly(k)}</dt>
                    <dd>{friendly(v) || "—"}</dd>
                  </div>
                ))}
              </dl>
            </section>
            <details className="hr-source">
              <summary>{t("Original import data")}</summary>
              <p>{c.source}</p>
              <dl>
                {Object.entries(c.answers).map(([k, v]) => (
                  <div key={k}>
                    <dt>{friendly(k)}</dt>
                    <dd>{v || "—"}</dd>
                  </div>
                ))}
              </dl>
            </details>
            <details className="hr-source">
              <summary>{t("Change history")}</summary>
              {history.isError ? (
                <ErrorNotice retry={() => void history.refetch()}>
                  {errorMessage(history.error)}
                </ErrorNotice>
              ) : (
                history.data?.map((r) => (
                  <p key={r.id}>
                    {new Date(r.created_at).toLocaleString()} · {r.actor_name} ·{" "}
                    {t(r.action === "create" ? "Created" : "Updated")} ·{" "}
                    {r.fields
                      .filter((f) => !["fingerprint", "answers"].includes(f))
                      .join(", ")}
                  </p>
                ))
              )}
            </details>
          </div>
          {error && (
            <p role="alert" className="error-message">
              {error}
            </p>
          )}
        </div>
        <footer className="modal-footer">
          <Button disabled={busy} onClick={onClose}>
            {t(cardTab === "ai" ? "Close" : "Cancel")}
          </Button>
          {cardTab === "application" && (
            <Button type="submit" busy={busy} variant="primary">
              {t("Save changes")}
            </Button>
          )}
        </footer>
      </form>
    </Modal>
  );
}
function ImportDialog({
  vacancy,
  onClose,
  onDone,
}: {
  vacancy: Vacancy;
  onClose: () => void;
  onDone: (r: ImportResult) => void;
}) {
  const { t } = useI18n();
  const [batch, setBatch] = useState<Batch | null>(null);
  const [sheet, setSheet] = useState("");
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const current = batch?.sheets.find((s) => s.name === sheet);
  async function upload(file: File) {
    setError("");
    setBusy(true);
    try {
      if (file.size > 10 * 1024 * 1024)
        throw new Error(t("Maximum file size is 10 MB."));
      const f = new FormData();
      f.append("file", file);
      const b = await request<Batch>(`/hr/vacancies/${vacancy.id}/imports`, {
        method: "POST",
        body: f,
      });
      setBatch(b);
      setSheet(b.sheets[0].name);
      setMapping(b.sheets[0].mapping);
      setPreview(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function proceed(confirm = false) {
    setBusy(true);
    setError("");
    try {
      const r = await post<ImportResult>(
        `/hr/imports/${batch?.id}/${confirm ? "confirm" : "preview"}`,
        { sheet, mapping },
      );
      if (confirm) onDone(r);
      else setPreview(r);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Import candidates"
      wide
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <div className="modal-body">
        <p>
          <strong>{vacancy.name}</strong>
        </p>
        {!batch ? (
          <Field label="Excel workbook (.xlsx)">
            <input
              type="file"
              accept=".xlsx"
              disabled={busy}
              onChange={(e) => {
                if (e.target.files?.[0]) void upload(e.target.files[0]);
              }}
            />
          </Field>
        ) : (
          <>
            <div className="form-grid">
              <Field label="Worksheet">
                <Select
                  disabled={busy}
                  value={sheet}
                  onChange={(e) => {
                    const s = batch.sheets.find(
                      (s) => s.name === e.target.value,
                    )!;
                    setSheet(s.name);
                    setMapping(s.mapping);
                    setPreview(null);
                  }}
                >
                  {batch.sheets.map((s) => (
                    <option key={s.name} value={s.name}>
                      {s.name} ({s.count})
                    </option>
                  ))}
                </Select>
              </Field>
              {(["name", "email", "phone"] as const).map((k) => (
                <Field
                  label={
                    {
                      name: "Name column",
                      email: "Email column",
                      phone: "Phone column",
                    }[k]
                  }
                  key={k}
                >
                  <Select
                    disabled={busy}
                    value={mapping[k] || ""}
                    onChange={(e) => {
                      setMapping({ ...mapping, [k]: e.target.value });
                      setPreview(null);
                    }}
                  >
                    <option value="">{t("Not mapped")}</option>
                    {current?.columns.map((c) => (
                      <option key={c} value={c}>
                        {friendly(c)}
                      </option>
                    ))}
                  </Select>
                </Field>
              ))}
            </div>
            {preview && (
              <div className="hr-import-result" role="status">
                <strong>
                  {t("Ready to import")}: {preview.added}
                </strong>
                <p>
                  {t("Duplicates")}: {preview.duplicates} ·{" "}
                  {t("Incomplete rows")}: {preview.invalid} ·{" "}
                  {t("Facebook test leads")}: {preview.test_rows}
                </p>
                {preview.sample?.map((r, i) => (
                  <p key={i}>
                    {r.name} · {r.email || r.phone}
                  </p>
                ))}
              </div>
            )}
            <p className="hr-sort-note">
              {t(
                "All original answers are preserved. Existing candidates, notes and statuses are never overwritten.",
              )}
            </p>
          </>
        )}
        {busy && <Loading />}
        {error && (
          <p role="alert" className="error-message">
            {error}
          </p>
        )}
      </div>
      <footer className="modal-footer">
        <Button disabled={busy} onClick={onClose}>
          {t("Cancel")}
        </Button>
        {batch && (
          <Button
            busy={busy}
            variant="primary"
            disabled={!!preview && !preview.added}
            onClick={() => void proceed(!!preview)}
          >
            {t(preview ? "Confirm import" : "Check import")}
          </Button>
        )}
      </footer>
    </Modal>
  );
}
