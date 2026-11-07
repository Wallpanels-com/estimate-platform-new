import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { request, post, patch, errorMessage } from "../lib/api";
import { useHRStatuses, type HRStatus } from "../lib/hrStatuses";
import { useI18n } from "../lib/i18n";
import { Button, Field, Modal, ErrorNotice, useNotice } from "./ui";
import Select from "./Select";
export default function HRStatusManager({ close }: { close: () => void }) {
  const { t, language } = useI18n(),
    query = useHRStatuses(),
    client = useQueryClient(),
    notice = useNotice();
  const [edit, setEdit] = useState<HRStatus | null>(null),
    [en, setEn] = useState(""),
    [ru, setRu] = useState(""),
    [adding, setAdding] = useState(false),
    [deleting, setDeleting] = useState<HRStatus | null>(null),
    [replacement, setReplacement] = useState("new"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function save() {
    setBusy(true);
    setError("");
    try {
      const body = { name_en: en, name_ru: ru, version: edit?.version || 0 };
      if (edit) await patch("/hr/statuses/" + edit.key, body);
      else await post("/hr/statuses", body);
      setEdit(null);
      setAdding(false);
      await client.invalidateQueries({ queryKey: ["hr-statuses"] });
      await client.invalidateQueries({ queryKey: ["hr-candidates"] });
      notice(t("Status saved"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (
      !deleting ||
      !window.confirm(
        t("Delete this status and move its candidates to the selected status?"),
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await request("/hr/statuses/" + deleting.key, {
        method: "DELETE",
        body: JSON.stringify({ version: deleting.version, replacement }),
      });
      setDeleting(null);
      await client.invalidateQueries({ queryKey: ["hr-statuses"] });
      await client.invalidateQueries({ queryKey: ["hr-candidates"] });
      notice(t("Status deleted"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Manage statuses"
      onClose={() => {
        if (!busy) close();
      }}
    >
      <div className="modal-body hr-status-manager">
        {error && <ErrorNotice>{t(error)}</ErrorNotice>}
        {query.isError && (
          <ErrorNotice retry={() => void query.refetch()}>
            {t(errorMessage(query.error))}
          </ErrorNotice>
        )}
        {deleting ? (
          <>
            <p>
              {t("Move candidates before deleting status")}:{" "}
              <strong>
                {language === "ru" ? deleting.name_ru : deleting.name_en}
              </strong>
            </p>
            <Field label="Replacement status">
              <Select
                value={replacement}
                onChange={(e) => setReplacement(e.target.value)}
              >
                {query.data
                  ?.filter((s) => s.key !== deleting.key)
                  .map((s) => (
                    <option key={s.key} value={s.key}>
                      {language === "ru" ? s.name_ru : s.name_en}
                    </option>
                  ))}
              </Select>
            </Field>
            <div className="button-row">
              <Button disabled={busy} onClick={() => setDeleting(null)}>
                {t("Cancel")}
              </Button>
              <Button
                variant="primary"
                busy={busy}
                onClick={() => void remove()}
              >
                {t("Delete status")}
              </Button>
            </div>
          </>
        ) : edit || adding ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
          >
            <div className="form-grid">
              <Field label="Status name (EN)">
                <input
                  value={en}
                  required
                  maxLength={120}
                  onChange={(e) => setEn(e.target.value)}
                />
              </Field>
              <Field label="Status name (RU)">
                <input
                  value={ru}
                  maxLength={120}
                  onChange={(e) => setRu(e.target.value)}
                />
              </Field>
            </div>
            <div className="button-row">
              <Button
                disabled={busy}
                onClick={() => {
                  setEdit(null);
                  setAdding(false);
                }}
              >
                {t("Cancel")}
              </Button>
              <Button type="submit" variant="primary" busy={busy}>
                {t("Save status")}
              </Button>
            </div>
          </form>
        ) : (
          <>
            <div className="hr-status-list">
              {query.data?.map((s) => (
                <div key={s.key}>
                  <span>{language === "ru" ? s.name_ru : s.name_en}</span>
                  <small>{s.count}</small>
                  <Button
                    variant="ghost"
                    aria-label={t(
                      "Edit status {0}",
                      language === "ru" ? s.name_ru : s.name_en,
                    )}
                    onClick={() => {
                      setEdit(s);
                      setEn(s.name_en);
                      setRu(s.name_ru);
                    }}
                  >
                    <Pencil size={16} />
                  </Button>
                  {s.key !== "new" && (
                    <Button
                      variant="ghost"
                      aria-label={t(
                        "Delete status {0}",
                        language === "ru" ? s.name_ru : s.name_en,
                      )}
                      onClick={() => {
                        setDeleting(s);
                        setReplacement("new");
                      }}
                    >
                      <Trash2 size={16} />
                    </Button>
                  )}
                </div>
              ))}
            </div>
            <Button
              onClick={() => {
                setAdding(true);
                setEn("");
                setRu("");
              }}
            >
              <Plus size={16} />
              {t("Add status")}
            </Button>
          </>
        )}
      </div>
      <footer className="modal-footer">
        <Button disabled={busy} onClick={close}>
          {t("Close")}
        </Button>
      </footer>
    </Modal>
  );
}
