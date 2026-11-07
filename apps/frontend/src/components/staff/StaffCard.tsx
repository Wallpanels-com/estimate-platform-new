import { useId, useState, type FormEvent, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  BriefcaseBusiness,
  Check,
  ExternalLink,
  FileText,
  Pause,
  Pencil,
  Save,
  UserRound,
  UserRoundX,
} from "lucide-react";
import { patch, errorMessage } from "../../lib/api";
import type { StaffDirectory, StaffMember } from "../../lib/staff";
import Select from "../Select";
import { StaffContacts, StaffReserveContacts } from "./StaffContacts";
import {
  documentCaption,
  documentLink,
  locationName,
} from "../../lib/staffProfile";
import { useI18n } from "../../lib/i18n";
import { Button, ErrorNotice, Field, Modal, useNotice } from "../ui";

type Tab = "overview" | "notes";
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
  const [saved, setSaved] = useState(person);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("overview");
  const dirty = JSON.stringify(form) !== JSON.stringify(saved);
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
      const updated = await patch<StaffMember>(`/hr/staff/${person.id}`, {
        version: saved.version,
        name: form.name,
        title: form.title,
        department: form.department,
        status: form.status,
        manager_id: form.manager_id,
        fields: form.fields,
        links: form.links,
      });
      await client.invalidateQueries({ queryKey: ["hr-staff"] });
      if (!editing && tab === "notes") {
        setForm(updated);
        setSaved(updated);
        notify(L("Notes saved", "Заметки сохранены"));
      } else {
        notify(L("Employee saved", "Сотрудник сохранён"));
        close();
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  const tabs = [
    ["overview", UserRound, L("Overview", "Обзор")],
    ["notes", FileText, L("Notes", "Заметки")],
  ] as const;
  const status = statuses.find(([s]) => s === form.status)!;
  const StatusIcon = status[1];
  const initials = form.name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((n) => n[0])
    .join("");
  const notes = [
    ...new Set([
      "N",
      "P",
      ...Object.keys(form.fields),
      ...Object.keys(form.links),
    ]),
  ].filter((k) => !new Set("ABCDEFGHIJKLMO".split("")).has(k));
  const visibleNotes = editing
    ? notes
    : notes.filter((k) => k === "N" || form.fields[k]?.trim() || form.links[k]);
  const caption = (key: string) =>
    key === "F"
      ? L("Telegram & phone", "Telegram и телефон")
      : key === "K"
        ? L("Email & PayPal", "Email и PayPal")
        : key === "O"
          ? L("Backup contacts", "Резервные контакты")
          : key === "N"
            ? L("Note", "Заметка")
            : key === "P"
              ? L("Additional note", "Дополнительная заметка")
              : label(key);
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
  const sourceField = (k: string, editable = editing) => (
    <Field key={k} label={caption(k)} className="staff-source-field">
      {editable ? (
        <div className="staff-edit-field">
          {notes.includes(k) ||
          ["F", "K", "O"].includes(k) ||
          (form.fields[k] || "").includes("\n") ? (
            <textarea
              rows={k === "N" ? 6 : 3}
              value={form.fields[k] || ""}
              maxLength={20000}
              onChange={(e) => field(k, e.target.value)}
              aria-label={caption(k)}
            />
          ) : (
            <input
              value={form.fields[k] || ""}
              maxLength={20000}
              onChange={(e) => field(k, e.target.value)}
              aria-label={caption(k)}
            />
          )}
          {form.links[k] && /https?:\/\//i.test(form.links[k]) && (
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
          <ReadValue
            value={
              k === "H"
                ? locationName(form.fields[k] || "")
                : form.fields[k] || ""
            }
          />
          {form.links[k] && /^https?:\/\//i.test(form.links[k]) && (
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
  const documentUrl = documentLink(form.fields.M, form.links.M);
  const docCaption = documentCaption(form.fields.M || "");
  const documents = (
    <Field label={L("Documents", "Документы")} className="staff-profile-full">
      {editing ? (
        <div className="staff-edit-field">
          {docCaption && (
            <input
              aria-label={L("Document name", "Название документа")}
              value={form.fields.M || ""}
              maxLength={20000}
              onChange={(e) => field("M", e.target.value)}
            />
          )}
          <input
            aria-label={L("Document URL", "Ссылка на документы")}
            type="url"
            placeholder="https://"
            value={
              form.links.M ?? (documentLink(form.fields.M) ? form.fields.M : "")
            }
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                fields: documentLink(person.fields.M)
                  ? { ...f.fields, M: e.target.value }
                  : f.fields,
                links: e.target.value
                  ? { ...f.links, M: e.target.value }
                  : Object.fromEntries(
                      Object.entries(f.links).filter(([k]) => k !== "M"),
                    ),
              }))
            }
          />
        </div>
      ) : (
        <div>
          {docCaption && <ReadValue value={docCaption} />}
          {documentUrl ? (
            <a
              className="staff-document button secondary"
              href={documentUrl}
              target="_blank"
              rel="noreferrer"
            >
              <ExternalLink size={14} />
              {L("Open link", "Открыть ссылку")}
            </a>
          ) : (
            !docCaption && <ReadValue value="" />
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
                      {["C", "D", "I", "J"].map((k) => sourceField(k))}
                    </>,
                    "staff-profile-employment",
                  )}
                  {panel(
                    L("Contact information", "Контактная информация"),
                    <UserRound size={17} />,
                    editing ? (
                      ["F", "K"].map((k) => sourceField(k))
                    ) : (
                      <StaffContacts
                        contact={form.fields.F || ""}
                        email={form.fields.K || ""}
                        ru={ru}
                      />
                    ),
                    `staff-profile-contacts ${editing ? "staff-profile-contacts-editing" : ""}`,
                  )}
                  {panel(
                    L("Personal information", "Личные сведения"),
                    <UserRound size={17} />,
                    <>
                      {["H", "L"].map((k) => sourceField(k))}
                      {documents}
                    </>,
                    "staff-profile-personal",
                  )}
                  {panel(
                    L("Backup contacts", "Резервные контакты"),
                    <UserRound size={17} />,
                    editing ? (
                      sourceField("O")
                    ) : (
                      <StaffReserveContacts value={form.fields.O || ""} />
                    ),
                    "staff-profile-reserve",
                  )}
                </div>
              </>
            )}
            {tab === "notes" &&
              panel(
                L("Notes", "Заметки"),
                <FileText size={17} />,
                visibleNotes.map((k) => sourceField(k, true)),
                "staff-profile-notes",
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
                {saved.updated_by || "—"}
                <span>
                  {new Date(saved.updated_at).toLocaleDateString(
                    ru ? "ru-RU" : "en-US",
                  )}
                </span>
              </>
            )}
          </p>
          <Button onClick={dismiss} disabled={busy}>
            {L("Close", "Закрыть")}
          </Button>
          {editing || tab === "notes" ? (
            <Button
              type="submit"
              variant="primary"
              busy={busy}
              disabled={!dirty}
            >
              <Save size={16} />
              {editing
                ? L("Save changes", "Сохранить изменения")
                : L("Save notes", "Сохранить заметки")}
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
