import { useState, type FormEvent } from "react";
import { Plus, X } from "lucide-react";
import {
  type BookCategory,
  type BookItem,
  localized,
} from "../../lib/pricebook";
import { post, request, errorMessage } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import { Button, ErrorNotice, Field, Modal } from "../ui";
import Select from "../Select";

export default function ItemForm({
  item,
  categoryId,
  categories,
  onClose,
  onSaved,
  initialName = "",
  addToZone = false,
}: {
  item?: BookItem;
  categoryId: string;
  categories: BookCategory[];
  onClose: () => void;
  onSaved: (saved: BookItem) => Promise<void>;
  initialName?: string;
  addToZone?: boolean;
}) {
  const { t, language } = useI18n();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [mode, setMode] = useState(item?.pricing_mode || "unit");
  const [parameters, setParameters] = useState(item?.parameters || []);
  const [saved, setSaved] = useState<BookItem | null>(null);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = Object.fromEntries(new FormData(event.currentTarget));
    const payload = {
      ...form,
      pricing_mode: mode,
      unit: mode === "fixed" ? "Fixed" : form.unit,
      unit_price: mode === "unpriced" ? null : form.unit_price,
      default_quantity: mode === "fixed" ? "1" : form.default_quantity,
      parameters,
      archived: item?.archived || false,
      expected_version: item?.version,
    };
    try {
      const record =
        saved ||
        (item
          ? await request<BookItem>(`/pricing/catalog/items/${item.id}`, {
              method: "PUT",
              body: JSON.stringify(payload),
            })
          : await post<BookItem>("/pricing/catalog/items", payload));
      // If adding to the estimate fails, retry with the persisted record rather
      // than creating a duplicate Price Book entry.
      setSaved(record);
      await onSaved(record);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={t(item ? "Edit catalogue item" : "Add catalogue item")}
      onClose={() => {
        if (!busy) onClose();
      }}
      wide
    >
      <form onSubmit={save}>
        <div className="modal-body">
          {error ? (
            <div className="book-item-error">
              <ErrorNotice>{error}</ErrorNotice>
            </div>
          ) : null}
          {addToZone ? (
            <p className="book-item-context" role="status">
              {t(
                saved
                  ? "Item saved to Price Book. Retry to add it to this zone."
                  : "Saving also adds this item to the current zone.",
              )}
            </p>
          ) : null}
          <fieldset
            className="form-grid book-item-form"
            disabled={busy || Boolean(saved)}
          >
            <Field label={t("Item name (EN)")}>
              <input
                name="name"
                defaultValue={item?.name ?? initialName}
                required
                maxLength={200}
              />
            </Field>
            <Field label={t("Item name (RU)")}>
              <input
                name="name_ru"
                defaultValue={item?.name_ru}
                maxLength={200}
              />
            </Field>
            <Field label={t("Category")}>
              <Select
                name="category_id"
                defaultValue={item?.category_id || categoryId}
              >
                {categories
                  .filter((c) => !c.archived)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {localized(c, language, t)}
                    </option>
                  ))}
              </Select>
            </Field>
            <Field label={t("Item kind")}>
              <Select
                name="kind"
                defaultValue={
                  item?.kind ||
                  (categoryId === "materials"
                    ? "material"
                    : categoryId === "services"
                      ? "service"
                      : "work")
                }
              >
                <option value="work">{t("Work item")}</option>
                <option value="material">{t("Material")}</option>
                <option value="service">{t("Service")}</option>
              </Select>
            </Field>
            <Field label={t("Description (EN)")}>
              <textarea
                name="description"
                defaultValue={item?.description}
                maxLength={2000}
                rows={2}
              />
            </Field>
            <Field label={t("Description (RU)")}>
              <textarea
                name="description_ru"
                defaultValue={item?.description_ru}
                maxLength={2000}
                rows={2}
              />
            </Field>
            <Field label={t("Pricing method")}>
              <Select
                value={mode}
                onChange={(e) =>
                  setMode(e.target.value as BookItem["pricing_mode"])
                }
              >
                <option value="unit">{t("Quantity × unit price")}</option>
                <option value="fixed">{t("Fixed total")}</option>
                <option value="unpriced">{t("Price to be confirmed")}</option>
              </Select>
            </Field>
            <Field label={t("Unit")}>
              <Select
                name="unit"
                defaultValue={item?.unit || "ea"}
                disabled={mode === "fixed"}
              >
                {["SF", "LF", "ea", "HR", "Fixed"].map((unit) => (
                  <option key={unit} value={unit}>
                    {t(unit)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label={t(mode === "fixed" ? "Fixed total ($)" : "Unit price ($)")}
            >
              <input
                name="unit_price"
                type="number"
                min="0"
                max="9999999999.99"
                step="0.01"
                defaultValue={item?.unit_price ?? ""}
                required={mode !== "unpriced"}
                disabled={mode === "unpriced"}
              />
            </Field>
            <Field label={t("Default quantity")}>
              <input
                name="default_quantity"
                type="number"
                min="0.01"
                max="999999"
                step="0.01"
                defaultValue={item?.default_quantity || "1"}
                required={mode !== "fixed"}
                disabled={mode === "fixed"}
              />
            </Field>
            <div className="span-all book-specifications">
              <div className="book-subheading">
                <h3>{t("Specifications")}</h3>
                <Button
                  variant="ghost"
                  disabled={parameters.length >= 12}
                  onClick={() =>
                    setParameters((old) => [...old, { name: "", value: "" }])
                  }
                >
                  <Plus size={15} />
                  {t("Add parameter")}
                </Button>
              </div>
              {parameters.map((p, index) => (
                <div className="book-specification" key={index}>
                  <Field label={t("Parameter name (EN)")}>
                    <input
                      value={p.name}
                      required
                      maxLength={80}
                      onChange={(e) =>
                        setParameters((old) =>
                          old.map((v, i) =>
                            i === index ? { ...v, name: e.target.value } : v,
                          ),
                        )
                      }
                    />
                  </Field>
                  <Field label={t("Parameter value (EN)")}>
                    <input
                      value={p.value}
                      required
                      maxLength={300}
                      onChange={(e) =>
                        setParameters((old) =>
                          old.map((v, i) =>
                            i === index ? { ...v, value: e.target.value } : v,
                          ),
                        )
                      }
                    />
                  </Field>
                  <Button
                    variant="ghost"
                    aria-label={t("Remove parameter {0}", index + 1)}
                    onClick={() =>
                      setParameters((old) => old.filter((_, i) => i !== index))
                    }
                  >
                    <X size={16} />
                  </Button>
                </div>
              ))}
            </div>
            <p className="form-hint span-all">
              {t(
                "English names and specifications are used in estimates and presentations. These items do not change automatic calculator rules.",
              )}
            </p>
          </fieldset>
        </div>
        <footer className="modal-footer">
          <Button onClick={onClose} disabled={busy}>
            {t("Cancel")}
          </Button>
          <Button type="submit" variant="primary" busy={busy}>
            {t(saved && addToZone ? "Add saved item to zone" : "Save item")}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}
