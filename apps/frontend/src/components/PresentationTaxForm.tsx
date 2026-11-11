import { useEffect, useState, type FormEvent } from "react";
import { Button, Field, Modal, ErrorNotice, Loading } from "./ui";
import Select from "./Select";
import { request, money, errorMessage } from "../lib/api";
import { useI18n } from "../lib/i18n";
import {
  taxPreview,
  type PresentationTax,
  type TaxSnapshot,
} from "../lib/presentationTax";

export default function PresentationTaxForm({
  estimateId,
  showTotal,
  onSave,
  onClose,
}: {
  estimateId: string;
  showTotal: boolean;
  onSave: (value: PresentationTax) => Promise<boolean>;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [snapshot, setSnapshot] = useState<TaxSnapshot | null>(null);
  const [options, setOptions] = useState<PresentationTax>({
    enabled: false,
    mode: "percent",
    rate: "7",
    amount: "0",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    setSnapshot(null);
    void request<TaxSnapshot>(`/estimates/${estimateId}/presentation-tax`, {
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setSnapshot(data);
          setOptions(data.options);
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(errorMessage(err));
      });
    return () => controller.abort();
  }, [estimateId, retry]);
  const values = snapshot ? taxPreview(snapshot.subtotal, options) : null;
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!snapshot || !values || busy) return;
    setError("");
    setBusy(true);
    const safe = {
      ...options,
      rate:
        options.enabled && options.mode === "percent"
          ? options.rate
          : snapshot.options.rate,
      amount:
        options.enabled && options.mode === "amount"
          ? options.amount
          : snapshot.options.amount,
    };
    try {
      if (await onSave(safe)) onClose();
      else setError(t("Tax settings could not be saved. Please try again."));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={t("Tax settings")}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <form onSubmit={submit}>
        <div className="modal-body tax-form-body">
          {error ? (
            <ErrorNotice
              retry={!snapshot ? () => setRetry((n) => n + 1) : undefined}
            >
              {t(error)}
            </ErrorNotice>
          ) : null}
          {!snapshot && !error ? <Loading label={t("Loading…")} /> : null}
          {snapshot ? (
            <>
              <label className="tax-enabled">
                <input
                  type="checkbox"
                  checked={options.enabled}
                  disabled={busy}
                  onChange={(e) =>
                    setOptions({ ...options, enabled: e.target.checked })
                  }
                />
                {t("Add tax to the presentation")}
              </label>
              <div className="form-grid">
                <Field label={t("Tax calculation")}>
                  <Select
                    value={options.mode}
                    disabled={!options.enabled || busy}
                    onChange={(e) =>
                      setOptions({
                        ...options,
                        mode: e.target.value as PresentationTax["mode"],
                      })
                    }
                  >
                    <option value="percent">{t("Percentage")}</option>
                    <option value="amount">{t("Fixed tax amount")}</option>
                  </Select>
                </Field>
                <Field
                  label={t(
                    options.mode === "percent"
                      ? "Tax rate (%)"
                      : "Tax amount ($)",
                  )}
                >
                  <input
                    name={
                      options.mode === "percent" ? "tax_rate" : "tax_amount"
                    }
                    type="number"
                    min="0"
                    max={options.mode === "percent" ? "100" : "999999999999.99"}
                    step={options.mode === "percent" ? "0.0001" : "0.01"}
                    required
                    disabled={!options.enabled || busy}
                    value={
                      options.mode === "percent" ? options.rate : options.amount
                    }
                    onChange={(e) =>
                      setOptions({
                        ...options,
                        [options.mode === "percent" ? "rate" : "amount"]:
                          e.target.value,
                      })
                    }
                  />
                </Field>
              </div>
              {values ? (
                <dl className="tax-totals" aria-live="polite">
                  <div>
                    <dt>{t("Subtotal (before tax)")}</dt>
                    <dd>{money(values.subtotal)}</dd>
                  </div>
                  <div>
                    <dt>{t("Tax")}</dt>
                    <dd>{money(values.tax)}</dd>
                  </div>
                  <div className="tax-grand">
                    <dt>{t("Grand total (with tax)")}</dt>
                    <dd>{money(values.grand_total)}</dd>
                  </div>
                </dl>
              ) : (
                <ErrorNotice>
                  {t("Enter a valid tax rate or amount.")}
                </ErrorNotice>
              )}
              {!showTotal ? (
                <p className="form-hint">
                  {t(
                    "The total block is hidden in PDF. Enable Σ to show Subtotal, Tax and Grand Total.",
                  )}
                </p>
              ) : null}
            </>
          ) : null}
        </div>
        <footer className="modal-footer">
          <Button disabled={busy} onClick={onClose}>
            {t("Cancel")}
          </Button>
          <Button
            type="submit"
            variant="primary"
            busy={busy}
            disabled={!snapshot || !values}
          >
            {t("Save tax settings")}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}
