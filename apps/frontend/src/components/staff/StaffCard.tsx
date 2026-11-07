import { useId, useState, type FormEvent, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BriefcaseBusiness,
  Check,
  ExternalLink,
  FileText,
  History,
  Pause,
  Pencil,
  Save,
  UserRound,
  UserRoundX,
} from "lucide-react";
import { request, patch, errorMessage } from "../../lib/api";
import type { StaffDirectory, StaffMember } from "../../lib/staff";
import Select from "../Select";
import { useI18n } from "../../lib/i18n";
import { Button, ErrorNotice, Field, Loading, Modal, useNotice } from "../ui";

type Tab = "overview" | "documents" | "history";
const statuses = [
  ["active", Check, "Active", "Работает"],
  ["paused", Pause, "Paused", "На паузе"],
  ["inactive", UserRoundX, "Inactive", "Не работает"],
] as const;

function ReadValue({ value }: { value: string }) {
  const [expanded, setExpanded] = useState(false);
  const { language } = useI18n();
  const ru = language === "ru";
  const long = value.length > 300 || value.split("\n").length > 5;
  return (
    <div className="staff-read-value">
      <div
        className={`staff-value ${long && !expanded ? "staff-value-clamped" : ""}`}
      >
        {value || "—"}
      </div>
      {long && (
        <Button
          variant="ghost"
          className="staff-read-more"
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "−" : "+"}{" "}
          <span>
            {expanded
              ? ru
                ? "Свернуть"
                : "Show less"
              : ru
                ? "Подробнее"
                : "Show more"}
          </span>
        </Button>
      )}
    </div>
  );
}

export default function StaffCard({
  person,
  directory,
  close,
  ru,
}: {
  person: StaffMember;
  directory: StaffDirectory;
  close: () => void;
  ru: boolean;
}) {
  const L = (en: string, r: string) => (ru ? r : en);
  const uid = useId();
  const client = useQueryClient();
  const notify = useNotice();
  const [form, setForm] = useState(person);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("overview");
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
    enabled: tab === "history",
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
  function label(key: string) {
    return (
      directory.columns[key]?.[ru ? 1 : 0] ||
      `${L("Source column", "Столбец")} ${key}`
    );
  }
  const field = (key: string, value: string) =>
    setForm((f) => ({ ...f, fields: { ...f.fields, [key]: value } }));
  async function save(e: FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      setTab("overview");
      setError(L("Enter the employee’s name.", "Укажите имя сотрудника."));
      return;
    }
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
  const tabs = [
    ["overview", UserRound, L("Overview", "Обзор")],
    ["documents", FileText, L("Documents & notes", "Документы и заметки")],
    ["history", History, L("History", "История")],
  ] as const;
  const status = statuses.find(([s]) => s === form.status)!;
  const StatusIcon = status[1];
  const initials = form.name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((n) => n[0])
    .join("");
  const documents = [
    ...new Set([
      "M",
      "N",
      "O",
      "P",
      ...Object.keys(form.fields),
      ...Object.keys(form.links),
    ]),
  ].filter((k) => !new Set("ABCDEFGHIJKL".split("")).has(k));
  const nameInput = (key: "name" | "title" | "department", caption: string) => (
    <Field
      label={caption}
      className={key === "name" ? "staff-profile-full" : undefined}
    >
      {editing ? (
        <input
          value={form[key]}
          required={key === "name"}
          maxLength={key === "department" ? 160 : 240}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
        />
      ) : (
        <ReadValue value={form[key]} />
      )}
    </Field>
  );
  const sourceField = (k: string) => (
    <Field key={k} label={label(k)} className="staff-source-field">
      {editing ? (
        <div className="staff-edit-field">
          {documents.includes(k) || (form.fields[k] || "").includes("\n") ? (
            <textarea
              rows={3}
              value={form.fields[k] || ""}
              maxLength={20000}
              onChange={(e) => field(k, e.target.value)}
              aria-label={label(k)}
            />
          ) : (
            <input
              value={form.fields[k] || ""}
              maxLength={20000}
              onChange={(e) => field(k, e.target.value)}
              aria-label={label(k)}
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
                        Object.entries(f.links).filter(([key]) => key !== k),
                      ),
                }))
              }
            />
          )}
        </div>
      ) : (
        <div>
          <ReadValue value={form.fields[k] || ""} />
          {form.links[k] && /^(https?:\/\/|mailto:)/i.test(form.links[k]) && (
            <a
              className="staff-document"
              href={form.links[k]}
              target="_blank"
              rel="noreferrer"
            >
              <ExternalLink size={14} />
              {L("Open link", "Открыть ссылку")}
            </a>
          )}
        </div>
      )}
    </Field>
  );
  const panel = (
    title: string,
    icon: ReactNode,
    children: ReactNode,
    className = "",
  ) => (
    <section className={`staff-profile-section ${className}`}>
      <h3>
        {icon}
        {title}
      </h3>
      <div className="staff-profile-fields">{children}</div>
    </section>
  );
  return (
    <Modal
      title={form.name || person.name}
      onClose={dismiss}
      wide
      className="staff-card"
      leading={
        <div className="staff-profile-avatar" aria-hidden="true">
          {initials}
        </div>
      }
      description={
        <div className="staff-profile-subtitle">
          <span>{form.title || L("Employee", "Сотрудник")}</span>
          <span
            className={`staff-profile-badge staff-profile-badge-${form.status}`}
          >
            <StatusIcon size={12} />
            {L(status[2], status[3])}
          </span>
        </div>
      }
    >
      <form className="staff-card-form" onSubmit={save}>
        <div
          className="staff-profile-tabs"
          role="tablist"
          aria-label={L("Employee information", "Сведения о сотруднике")}
        >
          {tabs.map(([id, Icon, text], index) => (
            <button
              key={id}
              type="button"
              role="tab"
              id={`${uid}-${id}`}
              aria-controls={`${uid}-panel`}
              aria-selected={tab === id}
              tabIndex={tab === id ? 0 : -1}
              onClick={() => setTab(id)}
              onKeyDown={(e) => {
                const n =
                  e.key === "ArrowRight"
                    ? (index + 1) % tabs.length
                    : e.key === "ArrowLeft"
                      ? (index + tabs.length - 1) % tabs.length
                      : e.key === "Home"
                        ? 0
                        : e.key === "End"
                          ? tabs.length - 1
                          : -1;
                if (n >= 0) {
                  e.preventDefault();
                  setTab(tabs[n][0]);
                  document.getElementById(`${uid}-${tabs[n][0]}`)?.focus();
                }
              }}
            >
              <Icon size={16} aria-hidden="true" />
              {text}
            </button>
          ))}
        </div>
        <div
          className="modal-body"
          role="tabpanel"
          id={`${uid}-panel`}
          aria-labelledby={`${uid}-${tab}`}
          tabIndex={0}
        >
          {error && <ErrorNotice>{error}</ErrorNotice>}
          <fieldset className="staff-profile-content" disabled={busy}>
            {tab === "overview" && (
              <>
                {editing && (
                  <div className="staff-profile-edit-heading">
                    <span>
                      {L(
                        "Editing employee information",
                        "Редактирование данных сотрудника",
                      )}
                    </span>
                    <div
                      className="staff-card-status"
                      role="group"
                      aria-label={L("Employment status", "Статус сотрудника")}
                    >
                      {statuses.map(([s, Icon, en, r]) => (
                        <Button
                          key={s}
                          variant={form.status === s ? "primary" : "ghost"}
                          aria-pressed={form.status === s}
                          onClick={() => setForm((f) => ({ ...f, status: s }))}
                        >
                          <Icon size={14} />
                          {L(en, r)}
                        </Button>
                      ))}
                    </div>
                  </div>
                )}
                <div className="staff-profile-grid">
                  {panel(
                    L("Employment", "Работа"),
                    <BriefcaseBusiness size={17} />,
                    <>
                      {editing && nameInput("name", L("Name", "Имя"))}
                      {nameInput("title", L("Position", "Должность"))}
                      {nameInput("department", L("Department", "Отдел"))}
                      <Field
                        label={L("Manager", "Руководитель")}
                        className="staff-profile-full"
                      >
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
                          <ReadValue
                            value={
                              directory.items.find(
                                (p) => p.id === form.manager_id,
                              )?.name || ""
                            }
                          />
                        )}
                      </Field>
                      {["C", "D", "I", "J"].map(sourceField)}
                    </>,
                    "staff-profile-employment",
                  )}
                  <div className="staff-profile-side">
                    {panel(
                      L("Contact information", "Контактная информация"),
                      <UserRound size={17} />,
                      ["F", "K", "H"].map(sourceField),
                    )}
                    {panel(
                      L("Personal information", "Личные сведения"),
                      <UserRound size={17} />,
                      sourceField("L"),
                    )}
                  </div>
                </div>
              </>
            )}
            {tab === "documents" &&
              panel(
                L(
                  "Documents & additional information",
                  "Документы и дополнительные сведения",
                ),
                <FileText size={17} />,
                documents.map(sourceField),
                "staff-profile-documents",
              )}
            {tab === "history" && (
              <section className="staff-profile-section">
                <h3>
                  <History size={17} />
                  {L("Change history", "История изменений")}
                </h3>
                {history.isLoading ? (
                  <Loading />
                ) : history.error ? (
                  <ErrorNotice>{errorMessage(history.error)}</ErrorNotice>
                ) : history.data?.length ? (
                  <ul className="staff-history">
                    {history.data.map((h) => (
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
                ) : (
                  <p className="staff-profile-empty">
                    {L("No changes recorded yet.", "Изменений пока нет.")}
                  </p>
                )}
                <p className="staff-source">
                  {L("Source", "Источник")}: {person.source_sheet} ·{" "}
                  {L("row", "строка")} {person.source_row}
                </p>
              </section>
            )}
          </fieldset>
        </div>
        <footer className="modal-footer staff-profile-footer">
          <p className="staff-save-meta">
            {dirty ? (
              L("Unsaved changes", "Есть несохранённые изменения")
            ) : (
              <>
                {L("Last edited by", "Последнее изменение")}:{" "}
                {person.updated_by || "—"}
                <span>
                  {new Date(person.updated_at).toLocaleDateString(
                    ru ? "ru-RU" : "en-US",
                  )}
                </span>
              </>
            )}
          </p>
          <Button onClick={dismiss} disabled={busy}>
            {L("Close", "Закрыть")}
          </Button>
          {editing ? (
            <Button
              type="submit"
              variant="primary"
              busy={busy}
              disabled={!dirty}
            >
              <Save size={16} />
              {L("Save changes", "Сохранить изменения")}
            </Button>
          ) : (
            <Button
              variant="primary"
              onClick={() => {
                setEditing(true);
                setTab("overview");
              }}
            >
              <Pencil size={16} />
              {L("Edit profile", "Редактировать")}
            </Button>
          )}
        </footer>
      </form>
    </Modal>
  );
}
