import { useState, type FormEvent } from "react";
import {
  type BookCategory,
  type BookItem,
  categoryAvailable,
  categoryLabel,
  orderedCategories,
} from "../../lib/pricebook";
import { post, request, errorMessage } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import { Button, ErrorNotice, Field, Modal, Confirm } from "../ui";
import Select from "../Select";
import ItemNameFields from "./ItemNameFields";

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
  const [translating, setTranslating] = useState(false);
  const [mode, setMode] = useState(item?.pricing_mode || "unit");
  const parameters = item?.parameters || [];
  const [saved, setSaved] = useState<BookItem | null>(null);
  const [pending, setPending] = useState<Record<string, unknown> | null>(null);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (translating || busy) return;
    const form = Object.fromEntries(new FormData(event.currentTarget));
    const payload = {
      ...form,
      description: item?.description || "",
      description_ru: item?.description_ru || "",
      pricing_mode: mode,
      unit: mode === "fixed" ? "Fixed" : form.unit,
      unit_price: mode === "unpriced" ? null : form.unit_price,
      default_quantity: mode === "fixed" ? "1" : form.default_quantity,
      parameters,
      archived: item?.archived || false,
      expected_version: item?.version,
    };
    if (saved) {
      await persist(payload);
      return;
    }
    setPending(payload);
  }
  async function persist(payload = pending) {
    if (!payload || busy) return;
    setBusy(true);
    setError("");
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
      setPending(null);
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
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
              <ItemNameFields
                initialName={item?.name ?? initialName}
                initialRussian={item?.name_ru || ""}
                onTranslating={setTranslating}
              />
              <Field label={t("Category")}>
                <Select
                  name="category_id"
                  defaultValue={item?.category_id || categoryId}
                >
                  {orderedCategories(categories)
                    .filter((c) => categoryAvailable(c, categories))
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {categoryLabel(c, categories, language, t)}
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
                label={t(
                  mode === "fixed" ? "Fixed total ($)" : "Unit price ($)",
                )}
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
              {t(saved && addToZone ? "Add saved item to zone" : "Save item")}
            </Button>
          </footer>
        </form>
      </Modal>
      {pending ? (
        <Confirm
          title={t(item ? "Save item changes?" : "Create this item?")}
          action={t("Confirm save")}
          variant="primary"
          busy={busy}
          onClose={() => setPending(null)}
          onConfirm={() => persist()}
        >
          {t(
            "Save “{0}” to the shared Price Book? Existing estimates will not change.",
            String(pending.name),
          )}
        </Confirm>
      ) : null}
    </>
  );
}
