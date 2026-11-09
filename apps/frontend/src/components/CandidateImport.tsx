import { useState } from "react";
import { Upload, Check, ChevronLeft } from "lucide-react";
import { request, post, errorMessage } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { Button, Field, Modal, Loading, ErrorNotice } from "./ui";
import Select from "./Select";

type Mapping = Record<string, string>;
type Sheet = {
  name: string;
  columns: string[];
  count: number;
  mapping: Mapping;
  answer_columns: string[];
  technical_columns: string[];
  sample: Record<string, string>[];
};
type Batch = { id: string; sheets: Sheet[] };
type Selection = { mapping: Mapping; answer_columns: string[] };
export type ImportResult = {
  added: number;
  duplicates: number;
  invalid: number;
  test_rows: number;
  sheets?: {
    name: string;
    valid: number;
    invalid: number;
    test_rows: number;
  }[];
  sample?: {
    name: string;
    email: string;
    phone: string;
    answers?: Record<string, string>;
  }[];
};
const friendly = (value: string) => value.replaceAll("_", " ");
function ready(selection: Selection) {
  const m = selection.mapping,
    used = Object.values(m).filter(Boolean);
  return Boolean(
    m.name &&
    (m.email || m.phone || m.telegram) &&
    new Set(used).size === used.length,
  );
}
export default function CandidateImport({
  vacancy,
  onClose,
  onDone,
}: {
  vacancy: { id: string; name: string };
  onClose: () => void;
  onDone: (result: ImportResult) => void;
}) {
  const { t } = useI18n();
  const [batch, setBatch] = useState<Batch | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [active, setActive] = useState("");
  const [selections, setSelections] = useState<Record<string, Selection>>({});
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const sheet = batch?.sheets.find((s) => s.name === active),
    selection = selections[active];
  const complete =
    picked.length > 0 &&
    picked.every((name) => selections[name] && ready(selections[name]));
  function change(next: Selection) {
    setSelections((current) => ({ ...current, [active]: next }));
    setPreview(null);
    setError("");
  }
  async function upload(file: File) {
    setError("");
    setBusy(true);
    try {
      if (file.size > 10 * 1024 * 1024)
        throw Error(t("Maximum file size is 10 MB."));
      const form = new FormData();
      form.append("file", file);
      const result = await request<Batch>(
        `/hr/vacancies/${vacancy.id}/imports`,
        { method: "POST", body: form },
      );
      setBatch(result);
      setPicked(result.sheets.map((s) => s.name));
      setActive(result.sheets[0].name);
      setSelections(
        Object.fromEntries(
          result.sheets.map((s) => [
            s.name,
            { mapping: s.mapping, answer_columns: s.answer_columns },
          ]),
        ),
      );
      setPreview(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function proceed(confirm = false) {
    if (!batch || !complete) return;
    setError("");
    setBusy(true);
    try {
      const result = await post<ImportResult>(
        `/hr/imports/${batch.id}/${confirm ? "confirm" : "preview"}`,
        {
          sheets: picked.map((name) => ({ sheet: name, ...selections[name] })),
        },
      );
      if (confirm) onDone(result);
      else setPreview(result);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  function toggleSheet(name: string, checked: boolean) {
    const next = checked ? [...picked, name] : picked.filter((s) => s !== name);
    setPicked(next);
    if (!next.includes(active)) setActive(next[0] || "");
    setPreview(null);
    setError("");
  }
  function mappingField(key: string, label: string) {
    return (
      <Field key={key} label={label}>
        <Select
          value={selection.mapping[key] || ""}
          onChange={(e) => {
            const mapping = { ...selection.mapping, [key]: e.target.value };
            change({
              mapping,
              answer_columns: selection.answer_columns.filter(
                (c) => !Object.values(mapping).includes(c),
              ),
            });
          }}
        >
          <option value="">{t("Not mapped")}</option>
          {sheet?.columns.map((column) => (
            <option key={column} value={column}>
              {friendly(column)}
            </option>
          ))}
        </Select>
      </Field>
    );
  }
  const questions =
    sheet?.columns.filter(
      (c) =>
        !Object.values(selection?.mapping || {}).includes(c) &&
        !sheet.technical_columns.includes(c),
    ) || [];
  return (
    <Modal
      title="Import candidates"
      wide
      className="hr-import-modal"
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <div className="modal-body hr-import-body">
        <div className="hr-import-heading">
          <strong>{vacancy.name}</strong>
          {batch && !preview && (
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => {
                setBatch(null);
                setError("");
              }}
            >
              {t("Replace file")}
            </Button>
          )}
        </div>
        {!batch ? (
          <Field label="Excel workbook (.xlsx)">
            <input
              type="file"
              accept=".xlsx"
              disabled={busy}
              onChange={(e) => {
                if (e.target.files?.[0]) void upload(e.target.files[0]);
              }}
            />
          </Field>
        ) : preview ? (
          <>
            <section
              className="hr-import-result"
              aria-label={t("Import preview")}
            >
              <h3>
                {t("Ready to import")}: {preview.added}
              </h3>
              <dl className="hr-import-counts">
                <div>
                  <dt>{t("Duplicates")}</dt>
                  <dd>{preview.duplicates}</dd>
                </div>
                <div>
                  <dt>{t("Incomplete rows")}</dt>
                  <dd>{preview.invalid}</dd>
                </div>
                <div>
                  <dt>{t("Facebook test leads")}</dt>
                  <dd>{preview.test_rows}</dd>
                </div>
              </dl>
              <p>
                {t("Selected worksheets")}: {picked.join(", ")}
              </p>
            </section>
            {Boolean(preview.sample?.length) && (
              <section className="hr-import-sample">
                <h3>{t("Candidate preview")}</h3>
                {preview.sample?.map((candidate, index) => (
                  <article key={index}>
                    <div>
                      <strong>{candidate.name}</strong>
                      <span>
                        {[candidate.email, candidate.phone]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </div>
                    <dl>
                      {Object.entries(candidate.answers || {})
                        .slice(0, 2)
                        .map(([question, answer]) => (
                          <div key={question}>
                            <dt>{friendly(question)}</dt>
                            <dd>{friendly(answer)}</dd>
                          </div>
                        ))}
                    </dl>
                  </article>
                ))}
              </section>
            )}
            <Button disabled={busy} onClick={() => setPreview(null)}>
              <ChevronLeft size={16} />
              {t("Edit import settings")}
            </Button>
          </>
        ) : (
          <fieldset
            disabled={busy}
            className="hr-form-fieldset hr-import-config"
          >
            <section>
              <h3>{t("Worksheets to import")}</h3>
              <div className="hr-import-sheets">
                {batch.sheets.map((s) => (
                  <label key={s.name}>
                    <input
                      type="checkbox"
                      checked={picked.includes(s.name)}
                      onChange={(e) => toggleSheet(s.name, e.target.checked)}
                    />
                    <span>
                      {s.name}
                      <small>{t("{0} rows", s.count)}</small>
                    </span>
                  </label>
                ))}
              </div>
            </section>
            {picked.length > 1 && (
              <div
                className="hr-import-tabs"
                role="tablist"
                aria-label={t("Worksheet settings")}
              >
                {picked.map((name) => (
                  <button
                    type="button"
                    key={name}
                    role="tab"
                    aria-selected={name === active}
                    onClick={() => setActive(name)}
                  >
                    {name}
                    {ready(selections[name]) && <Check size={14} />}
                  </button>
                ))}
              </div>
            )}
            {sheet && selection ? (
              <section
                className="hr-import-sheet-settings"
                role="tabpanel"
                aria-label={t("Worksheet settings")}
              >
                <div className="hr-import-section-heading">
                  <h3>{t("Contact columns")}</h3>
                  <span>{sheet.name}</span>
                </div>
                <div className="hr-import-contact-grid">
                  {mappingField("name", "Name column")}
                  {mappingField("email", "Email column")}
                  {mappingField("phone", "Phone column")}
                </div>
                <details className="hr-import-optional">
                  <summary>{t("Additional contact columns")}</summary>
                  <div className="form-grid">
                    {mappingField("last_name", "Last name column")}
                    {mappingField("telegram", "Telegram column")}
                  </div>
                </details>
                {!ready(selection) && (
                  <p className="hr-import-mapping-notice" role="status">
                    {t(
                      "Choose a name and at least one contact. Use a different column for each field.",
                    )}
                  </p>
                )}
                <div className="hr-import-section-heading">
                  <h3>{t("Application questions")}</h3>
                  <div className="button-row">
                    <Button
                      variant="ghost"
                      onClick={() =>
                        change({ ...selection, answer_columns: questions })
                      }
                    >
                      {t("Select all")}
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() =>
                        change({ ...selection, answer_columns: [] })
                      }
                    >
                      {t("Clear selection")}
                    </Button>
                  </div>
                </div>
                <div className="hr-import-questions">
                  {questions.map((column) => (
                    <label key={column}>
                      <input
                        type="checkbox"
                        checked={selection.answer_columns.includes(column)}
                        onChange={(e) =>
                          change({
                            ...selection,
                            answer_columns: e.target.checked
                              ? [...selection.answer_columns, column]
                              : selection.answer_columns.filter(
                                  (c) => c !== column,
                                ),
                          })
                        }
                      />
                      <span>
                        <strong>{friendly(column)}</strong>
                        <small>
                          {friendly(
                            sheet.sample.find((row) => row[column])?.[column] ||
                              "—",
                          ).slice(0, 180)}
                        </small>
                      </span>
                    </label>
                  ))}
                </div>
                {questions.length === 0 && (
                  <p className="hr-muted">
                    {t("No application questions in this worksheet.")}
                  </p>
                )}
                {sheet.technical_columns.length > 0 && (
                  <details className="hr-import-optional">
                    <summary>
                      {t(
                        "Excluded technical columns ({0})",
                        sheet.technical_columns.length,
                      )}
                    </summary>
                    <p className="hr-import-excluded">
                      {sheet.technical_columns.map(friendly).join(" · ")}
                    </p>
                  </details>
                )}
              </section>
            ) : (
              <p className="hr-muted">{t("Choose at least one worksheet.")}</p>
            )}
            <p className="form-hint">
              {t(
                "Only selected answers are added. Existing candidates, notes and statuses stay unchanged. No AI tokens are used for import.",
              )}
            </p>
          </fieldset>
        )}
        {busy && <Loading />}
        {error && <ErrorNotice>{t(error)}</ErrorNotice>}
      </div>
      <footer className="modal-footer">
        <Button disabled={busy} onClick={onClose}>
          {t("Cancel")}
        </Button>
        {batch && (
          <Button
            busy={busy}
            variant="primary"
            disabled={!complete || Boolean(preview && !preview.added)}
            onClick={() => void proceed(Boolean(preview))}
          >
            <Upload size={16} />
            {t(preview ? "Confirm import" : "Check import")}
          </Button>
        )}
      </footer>
    </Modal>
  );
}
