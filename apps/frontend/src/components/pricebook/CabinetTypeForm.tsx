import { useRef, useState, type FormEvent } from "react";
import { request, errorMessage } from "../../lib/api";
import type { PricingConfig } from "../../lib/types";
import { useI18n } from "../../lib/i18n";
import { Button, Confirm, ErrorNotice, Field, Modal } from "../ui";
import ItemNameFields from "./ItemNameFields";

type Entry = { label: string; label_ru: string; base_rate: number };

/** Extend the existing LF calculator; never create a new calculation formula. */
export default function CabinetTypeForm({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: (key: string) => Promise<void>;
}) {
  const { t } = useI18n();
  const key = useRef(`custom_${crypto.randomUUID().replaceAll("-", "")}`);
  const savedEntry = useRef<Entry | null>(null);
  const [pending, setPending] = useState<Entry | null>(null);
  const [created, setCreated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [error, setError] = useState("");
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (created) {
      setPending(savedEntry.current);
      return;
    }
    const form = new FormData(event.currentTarget);
    setPending({
      label: String(form.get("name") || "").trim(),
      label_ru: String(form.get("name_ru") || "").trim(),
      base_rate: Number(form.get("rate")),
    });
  }
  async function save() {
    if (!pending || busy) return;
    setBusy(true);
    setError("");
    try {
      if (!created) {
        // Fetch immediately before the write; the revision prevents concurrent
        // changes by colleagues from being overwritten by this new entry.
        const current = await request<{
          config: PricingConfig;
          revision: string;
        }>("/pricing/config");
        const config = structuredClone(current.config);
        const cabinet = config.cabinet as Record<string, unknown>;
        cabinet.types = {
          ...(cabinet.types as Record<string, unknown>),
          [key.current]: pending,
        };
        await request("/pricing/config", {
          method: "PUT",
          body: JSON.stringify({ config, expected_revision: current.revision }),
        });
        savedEntry.current = pending;
        setCreated(true);
      }
      await onSaved(key.current);
      onClose();
    } catch (err) {
      setPending(null);
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Modal
        title={t("Add cabinet type")}
        onClose={() => {
          if (!busy) onClose();
        }}
      >
        <form onSubmit={submit}>
          <div className="modal-body">
            {error ? <ErrorNotice>{error}</ErrorNotice> : null}
            <fieldset className="form-grid" disabled={busy || created}>
              <ItemNameFields
                initialName=""
                initialRussian=""
                onTranslating={setTranslating}
              />
              <Field label={t("Price ({0})", "$/LF")} className="span-all">
                <input
                  name="rate"
                  type="number"
                  min="0"
                  max="9999999999.99"
                  step="0.01"
                  required
                />
              </Field>
            </fieldset>
          </div>
          <footer className="modal-footer">
            <Button onClick={onClose} disabled={busy}>
              {t("Cancel")}
            </Button>
            <Button
              type="submit"
              variant="primary"
              busy={busy}
              disabled={translating}
            >
              {t("Save cabinet type")}
            </Button>
          </footer>
        </form>
      </Modal>
      {pending ? (
        <Confirm
          title={t("Save cabinet type?")}
          action={t("Confirm save")}
          variant="primary"
          busy={busy}
          onClose={() => setPending(null)}
          onConfirm={save}
        >
          {t(
            "Save “{0}” to the shared Price Book? Existing estimates will not change.",
            pending.label,
          )}
        </Confirm>
      ) : null}
    </>
  );
}
