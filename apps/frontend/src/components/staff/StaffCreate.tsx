import { useState, type FormEvent } from "react";
import { UserPlus } from "lucide-react";
import { Button, Field, Modal, ErrorNotice } from "../ui";
import Select from "../Select";
import type { StaffMember } from "../../lib/staff";
import type { NewStaff } from "../../lib/staffChart";

export default function StaffCreate({
  people,
  department,
  manager,
  ru,
  busy,
  error,
  close,
  submit,
}: {
  people: StaffMember[];
  department: string;
  manager: string | null;
  ru: boolean;
  busy: boolean;
  error: string;
  close: () => void;
  submit: (value: NewStaff) => Promise<void>;
}) {
  const L = (en: string, r: string) => (ru ? r : en);
  const [form, setForm] = useState<NewStaff>(() => ({
    id: crypto.randomUUID(),
    name: "",
    title: "",
    status: "active",
    department,
    manager_id: manager,
    contact: "",
    email: "",
    notes: "",
  }));
  const [localError, setLocalError] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!form.name.trim()) {
      setLocalError(L("Enter the employee’s name.", "Укажите имя сотрудника."));
      return;
    }
    setLocalError("");
    await submit(form);
  }
  return (
    <Modal
      title={L("Add employee", "Добавить сотрудника")}
      wide
      onClose={() => {
        if (!busy) close();
      }}
    >
      <form onSubmit={save}>
        <div className="modal-body">
          <fieldset className="form-grid staff-create-fields" disabled={busy}>
            <Field label={L("Full name", "Имя и фамилия")}>
              <input
                autoFocus
                required
                maxLength={240}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </Field>
            <Field label={L("Position", "Должность")}>
              <input
                maxLength={240}
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </Field>
            <Field label={L("Department", "Отдел")}>
              <input
                maxLength={160}
                value={form.department}
                onChange={(e) =>
                  setForm({ ...form, department: e.target.value })
                }
              />
            </Field>
            <Field label={L("Status", "Статус")}>
              <Select
                value={form.status}
                onChange={(e) =>
                  setForm({
                    ...form,
                    status: e.target.value as NewStaff["status"],
                  })
                }
              >
                <option value="active">{L("Active", "Работает")}</option>
                <option value="paused">{L("Paused", "На паузе")}</option>
                <option value="inactive">{L("Inactive", "Не работает")}</option>
              </Select>
            </Field>
            <Field label={L("Reports to", "Руководитель")}>
              <Select
                value={form.manager_id || ""}
                onChange={(e) =>
                  setForm({ ...form, manager_id: e.target.value || null })
                }
              >
                <option value="">{L("No manager", "Без руководителя")}</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={L("Email", "Электронная почта")}>
              <input
                type="email"
                maxLength={320}
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </Field>
            <Field label={L("Phone or Telegram", "Телефон или Telegram")}>
              <input
                maxLength={500}
                value={form.contact}
                onChange={(e) => setForm({ ...form, contact: e.target.value })}
              />
            </Field>
            <Field label={L("Notes", "Заметки")}>
              <textarea
                rows={2}
                maxLength={20000}
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </Field>
          </fieldset>
          {(error || localError) && (
            <ErrorNotice>{error || localError}</ErrorNotice>
          )}
        </div>
        <footer className="modal-footer">
          <Button disabled={busy} onClick={close}>
            {L("Cancel", "Отмена")}
          </Button>
          <Button type="submit" variant="primary" busy={busy}>
            <UserPlus size={16} />
            {L("Create employee & save chart", "Создать и сохранить схему")}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}
