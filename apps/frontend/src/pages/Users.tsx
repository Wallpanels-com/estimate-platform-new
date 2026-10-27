import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, KeyRound, Pencil } from "lucide-react";
import { request, post, patch, errorMessage } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import type { User } from "../lib/types";
import { Button, Field, Modal, Loading, ErrorNotice } from "../components/ui";
import Select from "../components/Select";

export default function Users() {
  const { t } = useI18n();
  const { user: me, signOut } = useAuth();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["team-users"],
    queryFn: () => request<User[]>("/users"),
  });
  const [editing, setEditing] = useState<User | "new" | null>(null);
  const [passwordUser, setPasswordUser] = useState<User | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function close() {
    if (!busy) {
      setEditing(null);
      setPasswordUser(null);
      setError("");
    }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      if (passwordUser)
        await post(`/users/${passwordUser.id}/password`, {
          password: form.get("password"),
        });
      else if (editing === "new")
        await post("/users", Object.fromEntries(form));
      else if (editing)
        await patch(`/users/${editing.id}`, {
          email: form.get("email"),
          name: form.get("name"),
          role: form.get("role") || editing.role,
          is_active:
            editing.id === me?.id
              ? editing.is_active
              : form.get("is_active") === "true",
        });
      if (
        passwordUser?.id === me?.id ||
        (editing &&
          editing !== "new" &&
          editing.id === me?.id &&
          String(form.get("email")).trim().toLowerCase() !== me.email)
      ) {
        signOut();
        return;
      }
      await client.invalidateQueries({ queryKey: ["me"] });
      await client.invalidateQueries({ queryKey: ["team-users"] });
      setEditing(null);
      setPasswordUser(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="team-page">
      <header className="page-heading">
        <div>
          <h1>{t("Team accounts")}</h1>
          <p>
            {t(
              "Everyone has the same access to all estimates and the Price Book.",
            )}
          </p>
        </div>
        <Button variant="primary" onClick={() => setEditing("new")}>
          <Plus size={17} />
          {t("Add employee")}
        </Button>
      </header>
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <ErrorNotice>{errorMessage(query.error)}</ErrorNotice>
      ) : (
        <div className="team-table-wrap">
          <table className="team-table">
            <thead>
              <tr>
                <th>{t("Name")}</th>
                <th>{t("Login")}</th>
                <th>{t("Role")}</th>
                <th>{t("Status")}</th>
                <th>{t("Actions")}</th>
              </tr>
            </thead>
            <tbody>
              {query.data?.map((user) => (
                <tr key={user.id}>
                  <td>{user.name}</td>
                  <td>{user.email}</td>
                  <td>{t("User")}</td>
                  <td>{t(user.is_active ? "Active" : "Disabled")}</td>
                  <td>
                    <div className="row-actions">
                      <Button onClick={() => setEditing(user)}>
                        <Pencil size={15} />
                        {t("Edit")}
                      </Button>
                      <Button onClick={() => setPasswordUser(user)}>
                        <KeyRound size={15} />
                        {t("Reset password")}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing || passwordUser ? (
        <Modal
          title={t(
            passwordUser
              ? "Reset password"
              : editing === "new"
                ? "Add employee"
                : "Edit employee",
          )}
          onClose={close}
        >
          <form onSubmit={submit}>
            <div className="modal-body form-grid">
              {error ? (
                <div className="span-2">
                  <ErrorNotice>{error}</ErrorNotice>
                </div>
              ) : null}
              {!passwordUser ? (
                <>
                  <Field label="Name">
                    <input
                      name="name"
                      defaultValue={
                        editing && editing !== "new" ? editing.name || "" : ""
                      }
                      required
                      maxLength={120}
                    />
                  </Field>
                  <Field
                    label="Login"
                    hint={
                      editing !== "new"
                        ? "Changing a login signs this employee out. Their estimates and history are kept."
                        : undefined
                    }
                  >
                    <input
                      name="email"
                      type="text"
                      autoComplete="off"
                      defaultValue={
                        editing && editing !== "new" ? editing.email : ""
                      }
                      required
                      minLength={3}
                      maxLength={254}
                    />
                  </Field>
                  {editing !== "new" ? (
                    <Field label="Status">
                      <Select
                        name="is_active"
                        defaultValue={String(editing?.is_active)}
                        disabled={editing?.id === me?.id}
                      >
                        <option value="true">{t("Active")}</option>
                        <option value="false">{t("Disabled")}</option>
                      </Select>
                    </Field>
                  ) : null}
                </>
              ) : (
                <p className="span-2">
                  {passwordUser.name} · {passwordUser.email}
                </p>
              )}
              {editing === "new" || passwordUser ? (
                <Field
                  label="Temporary password"
                  hint="At least 12 characters. Send it to this employee privately."
                >
                  <input
                    name="password"
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={12}
                    maxLength={72}
                  />
                </Field>
              ) : null}
            </div>
            <footer className="modal-footer">
              <Button onClick={close} disabled={busy}>
                {t("Cancel")}
              </Button>
              <Button type="submit" variant="primary" busy={busy}>
                {t("Save")}
              </Button>
            </footer>
          </form>
        </Modal>
      ) : null}
    </div>
  );
}
