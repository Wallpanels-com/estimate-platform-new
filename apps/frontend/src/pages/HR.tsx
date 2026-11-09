import { canAccess } from "../lib/access";
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
  UsersRound,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { request, post, patch, errorMessage } from "../lib/api";
import { useI18n } from "../lib/i18n";
import {
  ModalPresence,
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
import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import HRStatusSelect from "../components/HRStatusSelect";
import HRStatusManager from "../components/HRStatusManager";
import ManualCandidate from "../components/ManualCandidate";
import CandidateFiles from "../components/CandidateFiles";
import { defaultStatuses, statusLabel, useHRStatuses } from "../lib/hrStatuses";
import { criteria } from "../lib/hrText";
import CandidateAI from "../components/CandidateAI";
import ImportDialog, { type ImportResult } from "../components/CandidateImport";
import { useHRLocalization } from "../lib/hrLocalization";

type Vacancy = {
  id: string;
  name: string;
  description: string;
  archived: boolean;
  updated_at: string;
  count: number;
};
export type Candidate = {
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
  const { user } = useAuth();
  const { t, language } = useI18n();
  const client = useQueryClient();
  const notify = useNotice();
  const vacancies = useQuery({
    queryKey: ["hr-vacancies"],
    queryFn: () => request<Vacancy[]>("/hr/vacancies"),
  });
  const vacancyText = useHRLocalization(
    { scope: "vacancies" },
    (vacancies.data || []).flatMap((v) => [v.name, v.description]),
  );
  const [selected, setSelected] = useState("");
  const [showArchive, setShowArchive] = useState(false);
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const statusesQuery = useHRStatuses();
  const statuses = statusesQuery.data || defaultStatuses;
  const [manageStatuses, setManageStatuses] = useState(false);
  const [addingCandidate, setAddingCandidate] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    contact: "",
    notes: false,
    score_min: "",
    score_max: "",
    created_from: "",
    created_to: "",
  });
  const filterCount = Object.values(filters).filter(Boolean).length;
  useEffect(() => {
    if (status && !statuses.some((s) => s.key === status)) setStatus("");
  }, [statusesQuery.data, status]);
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
      filters,
    ],
    enabled: !!ident,
    queryFn: () =>
      request<Results>(
        `/hr/vacancies/${ident}/candidates?${new URLSearchParams({
          ...Object.fromEntries(
            Object.entries(filters)
              .filter(([, v]) => v !== false && v !== "")
              .map(([k, v]) => [
                k,
                k.startsWith("created_") ? String(v) + "T00:00:00Z" : String(v),
              ]),
          ),
          q: search,
          status: status || "",
          priority: String(priority),
          page: String(page),
          page_size: String(pageSize),
          hidden: String(hiddenView),
        })
          .toString()
          .replace("status=&", "")}`,
      ),
    refetchInterval: 20000,
    refetchOnWindowFocus: true,
  });
  const skillsText = useHRLocalization(
    {
      scope: "candidates",
      candidate_ids: (query.data?.items || []).map((c) => c.id),
    },
    (query.data?.items || []).flatMap((c) =>
      c.evidence.slice(0, 2).map((e) => e.answer),
    ),
  );
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
  return (
    <div className="hr-page">
      <header className="page-header">
        <div className="min-zero">
          <h1>{t("HR department")}</h1>
        </div>
        <div className="page-actions">
          {canAccess(user, "hr") && (
            <Link className="button" to="/hr/staff">
              <UsersRound size={17} />
              {language === "ru" ? "Сотрудники" : "Staff"}
            </Link>
          )}
          <Button
            disabled={!current || current.archived}
            onClick={() => setAddingCandidate(true)}
          >
            <Plus size={17} />
            {t("Add candidate")}
          </Button>
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
                    {vacancyText.display(v.name)}
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
                  <h2>{vacancyText.display(current.name)}</h2>
                  {current.description && (
                    <p className="hr-description">
                      {vacancyText.translating
                        ? t("Translating HR content…")
                        : vacancyText.display(current.description)}
                    </p>
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
                <HRStatusSelect
                  all
                  value={status}
                  onChange={(v) => {
                    setStatus(v);
                    setPage(1);
                  }}
                  onManage={() => setManageStatuses(true)}
                />
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
                <Button
                  aria-expanded={showFilters}
                  onClick={() => setShowFilters(!showFilters)}
                >
                  <SlidersHorizontal size={17} />
                  {t("Filters")}
                  {filterCount > 0 && <span>{filterCount}</span>}
                </Button>
              </div>
              {showFilters && (
                <div className="hr-filter-panel form-grid">
                  <Field label="Contact available">
                    <Select
                      value={filters.contact}
                      onChange={(e) => {
                        setFilters({ ...filters, contact: e.target.value });
                        setPage(1);
                      }}
                    >
                      <option value="">{t("Any contact")}</option>
                      <option value="email">{t("Email")}</option>
                      <option value="phone">{t("Phone")}</option>
                      <option value="telegram">Telegram</option>
                    </Select>
                  </Field>
                  <Field label="Notes">
                    <Select
                      value={String(filters.notes)}
                      onChange={(e) => {
                        setFilters({
                          ...filters,
                          notes: e.target.value === "true",
                        });
                        setPage(1);
                      }}
                    >
                      <option value="false">{t("Any candidate")}</option>
                      <option value="true">{t("With HR notes")}</option>
                    </Select>
                  </Field>
                  {(
                    [
                      ["score_min", "Minimum match"],
                      ["score_max", "Maximum match"],
                      ["created_from", "Added from"],
                      ["created_to", "Added through"],
                    ] as const
                  ).map(([key, label]) => (
                    <Field key={key} label={label}>
                      <input
                        type={key.startsWith("created_") ? "date" : "number"}
                        min={key.startsWith("score_") ? 0 : undefined}
                        max={key.startsWith("score_") ? 100 : undefined}
                        value={filters[key]}
                        onChange={(e) => {
                          setFilters({ ...filters, [key]: e.target.value });
                          setPage(1);
                        }}
                      />
                    </Field>
                  ))}
                  <div className="span-all">
                    <Button
                      variant="ghost"
                      disabled={!filterCount}
                      onClick={() => {
                        setFilters({
                          contact: "",
                          notes: false,
                          score_min: "",
                          score_max: "",
                          created_from: "",
                          created_to: "",
                        });
                        setPage(1);
                      }}
                    >
                      <X size={15} />
                      {t("Clear filters")}
                    </Button>
                  </div>
                </div>
              )}
              {language === "en" && skillsText.isError && (
                <ErrorNotice retry={() => void skillsText.refetch()}>
                  {t("Could not translate the HR content. Please try again.")}
                </ErrorNotice>
              )}
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
                          <th className="hr-number">№</th>
                          <th>{t("Candidate")}</th>
                          <th>{t("Experience & skills")}</th>
                          <th>{t("Candidate status")}</th>
                          <th>{t("Actions")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {query.data.items.map((c, index) => (
                          <tr
                            key={c.id}
                            className={c.priority ? "hr-priority" : ""}
                          >
                            <td className="hr-number">
                              {(query.data!.page - 1) * pageSize + index + 1}
                            </td>
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
                                {c.evidence.slice(0, 2).map((e) => (
                                  <span key={e.criterion}>
                                    {t(criteria[e.criterion] || e.criterion)}:{" "}
                                    {skillsText.translating
                                      ? "…"
                                      : skillsText.display(e.answer)}
                                  </span>
                                ))}
                              </div>
                            </td>
                            <td>
                              <span
                                className={`hr-status hr-status-${c.status}`}
                              >
                                {statusLabel(statuses, c.status, language)}
                              </span>
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
                    sizeControl={
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
                    }
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
      <ModalPresence>
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
      </ModalPresence>
      <ModalPresence>
        {candidate && (
          <CandidateCard
            initial={candidate}
            focusNotes={notesFocus}
            onManageStatuses={() => setManageStatuses(true)}
            onClose={() => setCandidate(null)}
            onSaved={(c) => {
              setCandidate(c);
              refresh();
            }}
          />
        )}
      </ModalPresence>
      <ModalPresence>
        {manageStatuses && (
          <HRStatusManager close={() => setManageStatuses(false)} />
        )}
      </ModalPresence>
      <ModalPresence>
        {addingCandidate && ident && (
          <ManualCandidate
            vacancyId={ident}
            close={() => setAddingCandidate(false)}
            onManage={() => setManageStatuses(true)}
            saved={(c) => {
              setAddingCandidate(false);
              setCandidate(c);
              void refresh();
              notify(t("Candidate added"));
            }}
          />
        )}
      </ModalPresence>
      <ModalPresence>
        {importing && current && (
          <ImportDialog
            vacancy={{ ...current, name: vacancyText.display(current.name) }}
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
      </ModalPresence>
    </div>
  );
}
function CandidateCard({
  initial: c,
  focusNotes = false,
  onClose,
  onSaved,
  onManageStatuses,
}: {
  onManageStatuses: () => void;
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
  const { language } = useI18n();
  const answersText = useHRLocalization(
    { scope: "candidate", candidate_id: c.id },
    [
      ...professional(c.answers).flatMap(([question, answer]) => [
        question,
        answer,
      ]),
      ...c.evidence.flatMap((e) => [e.question, e.answer]),
    ],
    cardTab === "application",
  );
  const [draft, setDraft] = useState({
    status: c.status,
    notes: c.notes,
    telegram_username: c.telegram_username || "",
  });
  const dirty =
    draft.status !== c.status ||
    draft.notes !== c.notes ||
    draft.telegram_username !== (c.telegram_username || "");
  function dismiss() {
    if (!busy && (!dirty || window.confirm(t("Discard unsaved changes?"))))
      onClose();
  }
  async function star() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      onSaved(
        await patch<Candidate>(`/hr/candidates/${c.id}/quick`, {
          version: c.version,
          priority: !c.priority,
        }),
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSaved(
        await patch<Candidate>(`/hr/candidates/${c.id}`, {
          version: c.version,
          status: draft.status,
          priority: c.priority,
          location: c.location,
          location_verified: c.location_verified,
          notes: draft.notes,
          telegram_username: draft.telegram_username || null,
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
    <Modal title={c.name} wide className="hr-review-modal" onClose={dismiss}>
      <form onSubmit={save}>
        <div className="modal-body hr-candidate-body">
          <div className="hr-candidate-contact">
            <Button
              variant="ghost"
              className="hr-card-priority"
              aria-label={t(
                c.priority
                  ? "Remove candidate priority"
                  : "Prioritize candidate",
              )}
              aria-pressed={c.priority}
              disabled={busy}
              onClick={() => void star()}
            >
              <Star size={20} fill={c.priority ? "currentColor" : "none"} />
            </Button>
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
                <HRStatusSelect
                  value={draft.status}
                  onChange={(v) => setDraft({ ...draft, status: v })}
                  onManage={onManageStatuses}
                />
              </Field>
              <Field label="Telegram username" className="hr-telegram-field">
                <input
                  name="telegram_username"
                  maxLength={200}
                  value={draft.telegram_username}
                  onChange={(e) =>
                    setDraft({ ...draft, telegram_username: e.target.value })
                  }
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
                  value={draft.notes}
                  onChange={(e) =>
                    setDraft({ ...draft, notes: e.target.value })
                  }
                />
              </Field>
            </div>
            {answersText.translating && (
              <p role="status">{t("Translating HR content…")}</p>
            )}
            {language === "en" && answersText.isError && (
              <ErrorNotice retry={() => void answersText.refetch()}>
                {t("Could not translate the HR content. Please try again.")}
              </ErrorNotice>
            )}
            {!answersText.translating &&
              !(language === "en" && answersText.isError) && (
                <>
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
                          <dt>{answersText.display(e.question)}</dt>
                          <dd>
                            {answersText.display(e.answer) || "—"} · {e.points}/
                            {e.maximum}
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
                          <dt>{answersText.display(k)}</dt>
                          <dd>{answersText.display(v) || "—"}</dd>
                        </div>
                      ))}
                    </dl>
                  </section>
                </>
              )}
          </div>
          <CandidateFiles id={c.id} />
          {error && <ErrorNotice>{t(error)}</ErrorNotice>}
        </div>
        <footer className="modal-footer">
          <Button disabled={busy} onClick={dismiss}>
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
