import { useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ClipboardPaste,
  Plus,
  ScanText,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { Button, ErrorNotice, Field } from "./ui";
import Select from "./Select";
import { useI18n } from "../lib/i18n";
import { ApiError, errorMessage, money } from "../lib/api";
import {
  blankRow,
  calculation,
  cents,
  mismatch,
  parseList,
  payloadRow,
  rowError,
  type BatchRow,
  type BatchPayload,
  type ParseBatch,
} from "../lib/manualBatch";

export default function ManualBatch({
  onAdd,
  onParse,
  onClose,
  onBusy,
}: {
  onAdd: (data: BatchPayload) => Promise<void>;
  onParse?: ParseBatch;
  onClose: () => void;
  onBusy: (value: boolean) => void;
}) {
  const { t } = useI18n();
  const [rows, setRows] = useState<BatchRow[]>(() => [blankRow()]);
  const [text, setText] = useState("");
  const [pasting, setPasting] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [parsing, setParsing] = useState(false);
  const parsingRef = useRef(false);
  const [pending, setPending] = useState<BatchPayload | null>(null);
  const sending = useRef(false);
  const locked = busy || parsing || !!pending;
  const total = rows.reduce(
    (sum, row) => sum + (cents(row.total_price) ?? 0n),
    0n,
  );
  function update(id: string, patch: Partial<BatchRow>) {
    setRows((old) =>
      old.map((row) => {
        if (row.id !== id) return row;
        const next = {
          ...row,
          ...patch,
          accept_total: patch.accept_total ?? false,
        };
        if ("quantity" in patch || "unit_price" in patch) {
          if (!row.total_price || calculation(row) === row.total_price)
            next.total_price = calculation(next) ?? "";
        }
        return next;
      }),
    );
  }
  function move(index: number, step: number) {
    setRows((old) => {
      const next = [...old];
      [next[index], next[index + step]] = [next[index + step], next[index]];
      return next;
    });
  }
  function parse() {
    try {
      const parsed = parseList(text);
      if (!parsed.length) {
        setError(t("Paste at least one item."));
        return;
      }
      const existing = rows.filter(
        (r) =>
          r.name ||
          r.total_price ||
          r.quantity ||
          r.unit_price ||
          r.description,
      );
      if (existing.length + parsed.length > 200)
        throw new Error("Use up to 200 lines at a time.");
      setRows([...existing, ...parsed]);
      setText("");
      setPasting(false);
      setError("");
    } catch (e) {
      setError(t(errorMessage(e)));
    }
  }
  async function parseWithAI() {
    if (!onParse || parsingRef.current || locked) return;
    if (
      text.length > 16000 ||
      text.split(/\r?\n/).filter((line) => line.trim()).length > 60
    ) {
      setError(
        t("Use up to 60 non-empty lines and 16000 characters for AI parsing."),
      );
      return;
    }
    parsingRef.current = true;
    setParsing(true);
    onBusy(true);
    setError("");
    try {
      const result = await onParse(text);
      const existing = rows.filter(
        (r) =>
          r.name ||
          r.total_price ||
          r.quantity ||
          r.unit_price ||
          r.description,
      );
      if (existing.length + result.rows.length > 200)
        throw new Error("Use up to 200 lines at a time.");
      setRows([
        ...existing,
        ...result.rows.map((row) => ({ ...blankRow(), ...row, review: true })),
      ]);
      setText("");
      setPasting(false);
    } catch (e) {
      setError(t(errorMessage(e)));
    } finally {
      parsingRef.current = false;
      setParsing(false);
      onBusy(false);
    }
  }
  async function save() {
    if (sending.current || parsingRef.current) return;
    const invalid = rows.find((row) => rowError(row));
    if (!pending && invalid) {
      setError(t(rowError(invalid)!));
      setOpen(invalid.id);
      return;
    }
    const data = pending ?? {
      request_id: crypto.randomUUID(),
      rows: rows.map(payloadRow),
    };
    sending.current = true;
    setBusy(true);
    onBusy(true);
    setPending(data);
    setError("");
    try {
      await onAdd(data);
      onClose();
    } catch (e) {
      setError(t(errorMessage(e)));
      if (e instanceof ApiError && e.status >= 400 && e.status < 500)
        setPending(null);
    } finally {
      sending.current = false;
      setBusy(false);
      onBusy(false);
    }
  }
  return (
    <>
      <div className="modal-body batch-editor">
        <div className="batch-toolbar">
          <span className="muted">
            {t("Add several items to this zone at once.")}
          </span>
          <Button
            disabled={locked}
            aria-expanded={pasting}
            onClick={() => setPasting(!pasting)}
          >
            <ClipboardPaste size={16} />
            {t("Paste list")}
          </Button>
        </div>
        {pasting && (
          <div className="batch-paste">
            <Field label={t("Paste your item list")}>
              <textarea
                rows={6}
                disabled={locked}
                value={text}
                maxLength={100000}
                onChange={(e) => setText(e.target.value)}
                placeholder={
                  "Kitchen cabinets — 17,6 Lin × 1200 = 21120\nGlass doors — 1500\nBar:\nShelves with LED — 600"
                }
              />
            </Field>
            <div className="button-row">
              <Button onClick={parse} disabled={!text.trim() || locked}>
                {t("Review list")}
              </Button>
              {onParse && (
                <Button
                  onClick={parseWithAI}
                  busy={parsing}
                  disabled={!text.trim() || locked}
                >
                  <ScanText size={16} />
                  {t(parsing ? "Parsing list…" : "Parse with AI")}
                </Button>
              )}
            </div>
          </div>
        )}
        {error ? <ErrorNotice>{error}</ErrorNotice> : null}
        {pending && !busy && (
          <p role="status">
            {t(
              "Retry the same batch to check whether it was saved. It will not be added twice.",
            )}
          </p>
        )}
        <div className="batch-columns" aria-hidden="true">
          <span>#</span>
          <span>{t("Item name")}</span>
          <span>{t("Total ($)")}</span>
          <span />
        </div>
        {rows.map((row, index) => (
          <div className="batch-entry" key={row.id}>
            <div className="batch-columns">
              <span className="batch-number">{index + 1}</span>
              <input
                aria-label={`${t("Item name")} ${index + 1}`}
                value={row.name}
                maxLength={500}
                disabled={locked}
                onChange={(e) => update(row.id, { name: e.target.value })}
              />
              <input
                aria-label={`${t("Total ($)")} ${index + 1}`}
                inputMode="decimal"
                value={row.total_price}
                disabled={locked}
                onChange={(e) =>
                  update(row.id, { total_price: e.target.value })
                }
              />
              <div className="batch-actions">
                <Button
                  className="icon-button"
                  aria-label={t("Item details")}
                  aria-expanded={open === row.id}
                  disabled={locked}
                  onClick={() => setOpen(open === row.id ? null : row.id)}
                >
                  <SlidersHorizontal size={16} />
                </Button>
                <Button
                  className="icon-button"
                  aria-label={t("Move up")}
                  disabled={locked || index === 0}
                  onClick={() => move(index, -1)}
                >
                  <ArrowUp size={15} />
                </Button>
                <Button
                  className="icon-button"
                  aria-label={t("Move down")}
                  disabled={locked || index === rows.length - 1}
                  onClick={() => move(index, 1)}
                >
                  <ArrowDown size={15} />
                </Button>
                <Button
                  className="icon-button"
                  aria-label={t("Remove row")}
                  disabled={locked}
                  onClick={() => setRows(rows.filter((r) => r.id !== row.id))}
                >
                  <Trash2 size={16} />
                </Button>
              </div>
            </div>
            {(row.review || mismatch(row)) && (
              <div className="batch-review">
                {row.source && <p className="batch-source">{row.source}</p>}
                {row.review && (
                  <label>
                    <input
                      type="checkbox"
                      disabled={locked}
                      checked={false}
                      onChange={() => update(row.id, { review: false })}
                    />
                    {t("I checked this line and its amount")}
                  </label>
                )}
                {mismatch(row) && (
                  <div className="button-row">
                    <span>
                      {t("Calculated total")}: {money(calculation(row))}
                    </span>
                    <Button
                      disabled={locked}
                      onClick={() =>
                        update(row.id, { total_price: calculation(row)! })
                      }
                    >
                      {t("Use calculated total")}
                    </Button>
                    <label>
                      <input
                        type="checkbox"
                        disabled={locked}
                        checked={row.accept_total}
                        onChange={(e) =>
                          update(row.id, { accept_total: e.target.checked })
                        }
                      />
                      {t("Keep entered total")}
                    </label>
                  </div>
                )}
              </div>
            )}
            {open === row.id && (
              <div className="batch-details form-grid">
                <Field label={t("Section")}>
                  <input
                    value={row.section}
                    maxLength={120}
                    disabled={locked}
                    onChange={(e) =>
                      update(row.id, { section: e.target.value })
                    }
                  />
                </Field>
                <Field label={t("Unit")}>
                  <Select
                    value={row.unit}
                    disabled={locked}
                    onChange={(e) =>
                      update(row.id, {
                        unit: e.target.value as BatchRow["unit"],
                      })
                    }
                  >
                    <option value="ea">{t("Each")}</option>
                    <option value="SF">SF</option>
                    <option value="LF">LF</option>
                  </Select>
                </Field>
                <Field label={t("Quantity")}>
                  <input
                    inputMode="decimal"
                    value={row.quantity}
                    disabled={locked}
                    onChange={(e) =>
                      update(row.id, { quantity: e.target.value })
                    }
                  />
                </Field>
                <Field label={t("Unit price ($)")}>
                  <input
                    inputMode="decimal"
                    value={row.unit_price}
                    disabled={locked}
                    onChange={(e) =>
                      update(row.id, { unit_price: e.target.value })
                    }
                  />
                </Field>
                <Field label={t("Description")} className="span-all">
                  <textarea
                    rows={2}
                    value={row.description}
                    maxLength={5000}
                    disabled={locked}
                    onChange={(e) =>
                      update(row.id, { description: e.target.value })
                    }
                  />
                </Field>
              </div>
            )}
          </div>
        ))}
        <div className="batch-toolbar">
          <Button
            disabled={locked || rows.length >= 200}
            onClick={() => setRows([...rows, blankRow(rows.at(-1)?.section)])}
          >
            <Plus size={16} />
            {t("Add row")}
          </Button>
          <strong>
            {t("Total")}: {money(Number(total) / 100)}
          </strong>
        </div>
      </div>
      <footer className="modal-footer">
        <Button disabled={busy || parsing} onClick={onClose}>
          {t("Cancel")}
        </Button>
        <Button
          variant="primary"
          busy={busy}
          disabled={!rows.length || parsing}
          onClick={save}
        >
          {t(pending ? "Retry save" : "Add items")}
        </Button>
      </footer>
    </>
  );
}
