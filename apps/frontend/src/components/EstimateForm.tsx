import Select from "./Select";
import { useI18n } from "../lib/i18n";
import { useState, type FormEvent } from "react";
import { Button, Field, Modal, ErrorNotice } from "./ui";
import { errorMessage } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Estimate } from "../lib/types";
import type { NewEstimateType } from "./NewEstimateButton";
import PreparedBy from "./PreparedBy";
export default function EstimateForm({
  estimate,
  initialType = "pre",
  onSave,
  onClose,
}: {
  estimate?: Estimate;
  initialType?: NewEstimateType;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onClose: () => void;
}) {
  const { t } = useI18n();

  const { user } = useAuth();
  const type = estimate?.type || initialType;
  const preparedBy = estimate?.prepared_by || user?.name || user?.email || "";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    const data: Record<string, unknown> = {
      ...f,
      ...(!estimate ? { type } : {}),
      title:
        f.title ||
        [
          f.client_name,
          f.project_name,
          type === "pre"
            ? "Pre-Estimate"
            : type === "quick"
              ? "Quick Estimate"
              : "Final Estimate",
        ]
          .filter(Boolean)
          .join(" - "),
    };
    for (const k of ["markup_pct", "discount_pct"])
      if (k in data) data[k] = data[k] === "" ? null : Number(data[k]);
    if (!data.project_name) data.project_name = null;
    setBusy(true);
    try {
      await onSave(data);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={
        estimate
          ? t("Estimate details")
          : t(type === "pre" ? "New pre-estimate" : "New final estimate")
      }
      onClose={onClose}
      wide
    >
      <form onSubmit={submit}>
        <div className="modal-body form-grid">
          {error ? (
            <div className="span-all">
              <ErrorNotice>{error}</ErrorNotice>
            </div>
          ) : null}
          <Field label={t("Client name")}>
            <input
              name="client_name"
              required
              autoComplete="off"
              defaultValue={estimate?.client_name || ""}
              maxLength={240}
            />
          </Field>
          <Field label={t("Project name")}>
            <input
              name="project_name"
              autoComplete="off"
              defaultValue={estimate?.project_name || ""}
              maxLength={300}
            />
          </Field>
          <Field
            label={t("Estimate title")}
            className="span-all"
            hint={t("Leave blank to use the client and project name.")}
          >
            <input
              name="title"
              autoComplete="off"
              defaultValue={estimate?.title || ""}
              maxLength={500}
            />
          </Field>
          <Field label={t("Estimate date")}>
            <input
              type="date"
              name="estimate_date"
              defaultValue={
                estimate?.estimate_date ||
                new Date().toLocaleDateString("en-CA")
              }
              required
            />
          </Field>
          {estimate ? (
            <Field label={t("Status")}>
              <Select name="status" defaultValue={estimate.status}>
                <option value="draft">{t("Draft")}</option>
                <option value="sent">{t("Sent")}</option>
                <option value="approved">{t("Approved")}</option>
              </Select>
            </Field>
          ) : (
            <PreparedBy name={preparedBy} />
          )}
          {estimate ? (
            <>
              <Field
                label={t("Markup (%)")}
                hint={t("Applied to client PDF prices.")}
              >
                <input
                  type="number"
                  min="0"
                  max="200"
                  step="0.5"
                  name="markup_pct"
                  defaultValue={estimate.markup_pct ?? ""}
                />
              </Field>
              <Field
                label={t("Discount (%)")}
                hint={t("Shown on the PDF project summary.")}
              >
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.5"
                  name="discount_pct"
                  defaultValue={estimate.discount_pct ?? ""}
                />
              </Field>
              <PreparedBy name={preparedBy} className="span-all" />
            </>
          ) : null}
        </div>
        <footer className="modal-footer">
          <Button onClick={onClose}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" busy={busy}>
            {estimate ? t("Save details") : t("Create estimate")}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}
