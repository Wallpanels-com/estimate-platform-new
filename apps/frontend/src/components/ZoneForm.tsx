import Select from "./Select";
import { useI18n } from "../lib/i18n";
import { useState, type FormEvent } from "react";
import { Button, ErrorNotice, Field, Modal } from "./ui";
import { errorMessage } from "../lib/api";
import type { Zone } from "../lib/types";
export default function ZoneForm({
  zone,
  count,
  onSave,
  onClose,
}: {
  zone?: Zone;
  count: number;
  onSave: (data: Record<string, unknown>) => Promise<void>;
  onClose: () => void;
}) {
  const { t } = useI18n();

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data: Record<string, unknown> = Object.fromEntries(
      new FormData(e.currentTarget),
    );
    for (const k of [
      "wall_width_ft",
      "wall_height_ft",
      "square_footage",
      "linear_footage",
    ])
      data[k] = data[k] === "" ? null : Number(data[k]);
    if (
      data.square_footage == null &&
      Number(data.wall_width_ft) > 0 &&
      Number(data.wall_height_ft) > 0
    )
      data.square_footage =
        Number(data.wall_width_ft) * Number(data.wall_height_ft);
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
    <Modal title={zone ? t("Edit zone") : t("Add zone")} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="modal-body form-grid">
          {error ? (
            <div className="span-all">
              <ErrorNotice>{error}</ErrorNotice>
            </div>
          ) : null}
          <Field label={t("Zone name")} className="span-all">
            <input
              name="label"
              defaultValue={zone?.label || `Zone ${count + 1}`}
              required
              autoComplete="off"
              maxLength={500}
            />
          </Field>
          <Field label={t("Zone type")}>
            <Select name="zone_type" defaultValue={zone?.zone_type || "wall"}>
              <option value="wall">{t("Wall panels")}</option>
              <option value="cabinet">{t("Cabinetry")}</option>
              <option value="mirror">{t("Mirror")}</option>
            </Select>
          </Field>
          <Field label={t("Room")}>
            <input
              name="room_name"
              defaultValue={zone?.room_name || ""}
              autoComplete="off"
            />
          </Field>
          <Field label={t("Wall name")} className="span-all">
            <input
              name="wall_name"
              defaultValue={zone?.wall_name || ""}
              autoComplete="off"
            />
          </Field>
          {[
            ["wall_width_ft", t("Width (ft)")],
            ["wall_height_ft", t("Height (ft)")],
            ["square_footage", t("Square footage (SF)")],
            ["linear_footage", t("Linear footage (LF)")],
          ].map(([key, label]) => (
            <Field key={key} label={label}>
              <input
                name={key}
                type="number"
                min="0"
                step="0.01"
                defaultValue={
                  (zone?.[key as keyof Zone] as string | number | null) ?? ""
                }
              />
            </Field>
          ))}
          <p className="form-hint span-all">
            {t(
              "Leave SF blank to calculate width × height. Existing line items keep their quantities.",
            )}
          </p>
          <Field label={t("Zone notes")} className="span-all">
            <textarea name="notes" rows={3} defaultValue={zone?.notes || ""} />
          </Field>
        </div>
        <footer className="modal-footer">
          <Button onClick={onClose}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary" busy={busy}>
            {zone ? t("Save zone") : t("Add zone")}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}
