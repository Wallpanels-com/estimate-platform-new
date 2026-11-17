import { useState, type FormEvent } from "react";
import { Button, Field, Modal, ErrorNotice } from "./ui";
import { money } from "../lib/api";
import { useI18n } from "../lib/i18n";

export type RangeOptions = {
  enabled: boolean;
  mode: "auto" | "manual";
  lower?: string | null;
  upper?: string | null;
};
export type ZoneRange = {
  options: RangeOptions;
  basis: string;
  automatic_lower: string;
  automatic_upper: string;
  lower: string;
  upper: string;
  stale: boolean;
};
export type RangeSnapshot = {
  active: boolean;
  zones: Record<string, ZoneRange>;
  lower: string;
  upper: string;
  grand_lower: string;
  grand_upper: string;
};
export const rangeLabel = (low: string, high: string) =>
  Number(low) === Number(high) ? money(low) : `${money(low)} – ${money(high)}`;

export default function ZoneRangeForm({
  label,
  value,
  onSave,
  onClose,
}: {
  label: string;
  value: ZoneRange;
  onSave: (options: RangeOptions) => Promise<boolean>;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [enabled, setEnabled] = useState(value.options.enabled);
  const [mode, setMode] = useState(value.options.mode);
  const [lower, setLower] = useState(
    value.options.lower ?? value.automatic_lower,
  );
  const [upper, setUpper] = useState(
    value.options.upper ?? value.automatic_upper,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const low = mode === "auto" ? value.automatic_lower : lower;
  const high = mode === "auto" ? value.automatic_upper : upper;
  const valid =
    !enabled ||
    (low.trim() !== "" &&
      high.trim() !== "" &&
      Number.isFinite(Number(low)) &&
      Number.isFinite(Number(high)) &&
      Number(low) >= 0 &&
      Number(high) >= Number(low));
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid || busy) return;
    setBusy(true);
    setError("");
    try {
      if (
        await onSave({
          enabled,
          mode,
          lower: mode === "manual" && enabled ? lower : null,
          upper: mode === "manual" && enabled ? upper : null,
        })
      )
        onClose();
      else setError(t("The price range could not be saved. Please try again."));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={t("Zone price range")}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <form onSubmit={submit}>
        <div className="modal-body zone-range-body">
          <p className="zone-range-name">{label}</p>
          <label className="tax-enabled">
            <input
              type="checkbox"
              checked={enabled}
              disabled={busy || Number(value.basis) <= 0}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            {t("Show a price range for this zone")}
          </label>
          {Number(value.basis) <= 0 ? (
            <p className="form-hint">
              {t(
                "Add confirmed positive pricing before enabling a zone range.",
              )}
            </p>
          ) : null}
          <p className="form-hint">
            {t("Calculation basis after discount")}:{" "}
            <strong>{money(value.basis)}</strong>
          </p>
          {enabled ? (
            <>
              <div
                className="zone-range-mode"
                role="group"
                aria-label={t("Range calculation")}
              >
                <Button
                  disabled={busy}
                  aria-pressed={mode === "auto"}
                  variant={mode === "auto" ? "primary" : "secondary"}
                  onClick={() => setMode("auto")}
                >
                  {t("Automatic")}
                </Button>
                <Button
                  disabled={busy}
                  aria-pressed={mode === "manual"}
                  variant={mode === "manual" ? "primary" : "secondary"}
                  onClick={() => {
                    if (mode === "auto") {
                      setLower(value.automatic_lower);
                      setUpper(value.automatic_upper);
                    }
                    setMode("manual");
                  }}
                >
                  {t("Set manually")}
                </Button>
              </div>
              <div className="form-grid">
                <Field label={t("From ($)")}>
                  <input
                    type="number"
                    min="0"
                    max="999999999999.99"
                    step="0.01"
                    required
                    disabled={busy || mode === "auto"}
                    value={low}
                    onChange={(e) => setLower(e.target.value)}
                  />
                </Field>
                <Field label={t("To ($)")}>
                  <input
                    type="number"
                    min="0"
                    max="999999999999.99"
                    step="0.01"
                    required
                    disabled={busy || mode === "auto"}
                    value={high}
                    onChange={(e) => setUpper(e.target.value)}
                  />
                </Field>
              </div>
              <p className="form-hint">
                {t(
                  mode === "auto"
                    ? "Automatic range: −10% / +15%. Updates when the zone changes."
                    : "Manual bounds stay fixed when the scope or discount changes. Prices are before tax.",
                )}
              </p>
              {value.stale && mode === "manual" ? (
                <p className="zone-range-warning" role="status">
                  {t(
                    "The zone or discount changed. Review the manual range before saving.",
                  )}
                </p>
              ) : null}
            </>
          ) : null}
          {!valid ? (
            <ErrorNotice>
              {t(
                "Enter a valid lower and upper price. The upper price must not be lower.",
              )}
            </ErrorNotice>
          ) : null}
          {error ? <ErrorNotice>{error}</ErrorNotice> : null}
          <div className="zone-range-result" aria-live="polite">
            <span>{t("Zone price in PDF")}</span>
            <strong>
              {enabled && valid ? rangeLabel(low, high) : money(value.basis)}
            </strong>
          </div>
          <p className="form-hint">
            {t(
              "With at least one zone range enabled, the project total sums all zone bounds. Other zones keep their exact prices. With all ranges off, the existing project range is used.",
            )}
          </p>
        </div>
        <footer className="modal-footer">
          <Button disabled={busy} onClick={onClose}>
            {t("Cancel")}
          </Button>
          <Button type="submit" variant="primary" busy={busy} disabled={!valid}>
            {t("Save")}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}
