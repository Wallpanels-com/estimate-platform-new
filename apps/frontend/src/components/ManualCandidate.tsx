import { useState, type FormEvent } from "react";
import { post, errorMessage } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { Button, Field, Modal, ErrorNotice } from "./ui";
import HRStatusSelect from "./HRStatusSelect";
import type { Candidate } from "../pages/HR";
export default function ManualCandidate({
  vacancyId,
  close,
  saved,
  onManage,
}: {
  vacancyId: string;
  close: () => void;
  saved: (c: Candidate) => void;
  onManage: () => void;
}) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [status, setStatus] = useState("new");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const body = Object.fromEntries(data.entries());
      const candidate = await post<Candidate>(
        `/hr/vacancies/${vacancyId}/candidates`,
        { ...body, status },
      );
      saved(candidate);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Add candidate"
      wide
      className="hr-create-candidate"
      onClose={() => {
        if (!busy) close();
      }}
    >
      <form onSubmit={submit}>
        <div className="modal-body">
          <fieldset disabled={busy} className="hr-form-fieldset">
            <div className="form-grid">
              <Field label="Candidate name" className="span-all">
                <input name="name" required maxLength={240} />
              </Field>
              <Field label="Email">
                <input name="email" type="email" maxLength={320} />
              </Field>
              <Field label="Phone">
                <input name="phone" maxLength={100} />
              </Field>
              <Field label="Telegram username">
                <input
                  name="telegram_username"
                  maxLength={200}
                  placeholder="@username"
                />
              </Field>
              <Field label="Candidate status">
                <HRStatusSelect
                  value={status}
                  onChange={setStatus}
                  onManage={onManage}
                />
              </Field>
              <Field label="Experience" className="span-all">
                <textarea name="experience" rows={3} maxLength={10000} />
              </Field>
              <Field label="English">
                <input name="english" maxLength={2000} />
              </Field>
              <Field label="US market">
                <input name="us_market" maxLength={2000} />
              </Field>
              <Field label="Technical drawings" className="span-all">
                <input name="drawings" maxLength={2000} />
              </Field>
              <Field label="HR notes" className="span-all">
                <textarea name="notes" rows={3} maxLength={20000} />
              </Field>
            </div>
          </fieldset>
          {error && <ErrorNotice>{t(error)}</ErrorNotice>}
        </div>
        <footer className="modal-footer">
          <Button disabled={busy} onClick={close}>
            {t("Cancel")}
          </Button>
          <Button type="submit" variant="primary" busy={busy}>
            {t("Add candidate")}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}
