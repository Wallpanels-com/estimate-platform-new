import { useState, type FormEvent } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button, Field, Modal, ErrorNotice } from "./ui";
import { Combobox } from "./Select";
import { useI18n } from "../lib/i18n";
import { errorMessage } from "../lib/api";

const presets = [
  "Bench is not included",
  "Staircase is not included",
  "Installation is not included",
].map((value) => ({ value, label: value }));
export default function PresentationNotesForm({
  label,
  notes,
  onSave,
  onClose,
}: {
  label: string;
  notes: string[];
  onSave: (notes: string[]) => Promise<boolean>;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [rows, setRows] = useState(() =>
    (notes.length ? notes : [""]).map((text) => ({
      id: crypto.randomUUID(),
      text,
    })),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      if (await onSave(rows.map((row) => row.text.trim()).filter(Boolean)))
        onClose();
      else setError(t("Notes could not be saved. Please try again."));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={t("Presentation notes")}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <form onSubmit={submit}>
        <div className="modal-body presentation-notes-body">
          <p className="presentation-notes-zone">{label}</p>
          <p className="form-hint">
            {t(
              "Choose a suggestion or type your own note. Notes appear after the scope, without a price, and do not affect totals.",
            )}
          </p>
          <div className="presentation-notes-list">
            {rows.map((row, index) => (
              <div className="presentation-note-row" key={row.id}>
                <Field label={t("Note {0}", index + 1)}>
                  <Combobox
                    hideEmptyMenu
                    options={presets}
                    defaultValue={row.text}
                    disabled={busy}
                    maxLength={1000}
                    placeholder={t("Choose or type a note…")}
                    onValueChange={(text) =>
                      setRows((current) =>
                        current.map((item) =>
                          item.id === row.id ? { ...item, text } : item,
                        ),
                      )
                    }
                  />
                </Field>
                <Button
                  variant="ghost"
                  disabled={busy}
                  aria-label={t("Delete note {0}", index + 1)}
                  title={t("Delete note {0}", index + 1)}
                  onClick={() =>
                    setRows((current) =>
                      current.filter((item) => item.id !== row.id),
                    )
                  }
                >
                  <Trash2 size={17} />
                </Button>
              </div>
            ))}
            {!rows.length ? (
              <p className="form-hint">
                {t("No presentation notes. Save to remove the existing notes.")}
              </p>
            ) : null}
          </div>
          <Button
            className="presentation-notes-add"
            disabled={busy || rows.length >= 20}
            onClick={() =>
              setRows((current) => [
                ...current,
                { id: crypto.randomUUID(), text: "" },
              ])
            }
          >
            <Plus size={16} />
            {t("Add note")}
          </Button>
          {rows.some((row) => row.text.trim()) ? (
            <div className="presentation-notes-preview" aria-live="polite">
              <span>{t("Text in the presentation")}</span>
              {rows
                .filter((row) => row.text.trim())
                .map((row) => (
                  <p key={row.id}>{row.text.trim()}</p>
                ))}
            </div>
          ) : null}
          {error ? <ErrorNotice>{error}</ErrorNotice> : null}
        </div>
        <footer className="modal-footer">
          <Button disabled={busy} onClick={onClose}>
            {t("Cancel")}
          </Button>
          <Button type="submit" variant="primary" busy={busy}>
            {t("Save")}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}
