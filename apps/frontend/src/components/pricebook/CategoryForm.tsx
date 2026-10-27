import { useState, type FormEvent } from "react";
import {
  type BookCategory,
  type CategoryIcon,
  categoryAvailable,
  categoryLabel,
  categoryTrail,
  orderedCategories,
} from "../../lib/pricebook";
import { post, request, errorMessage } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import { Button, ErrorNotice, Field, Modal, Confirm } from "../ui";
import Select from "../Select";
import CategoryIconPicker from "./CategoryIconPicker";

export default function CategoryForm({
  category,
  categories = [],
  parentId = null,
  onClose,
  onSaved,
}: {
  category?: BookCategory;
  categories?: BookCategory[];
  parentId?: string | null;
  onClose: () => void;
  onSaved: (category: BookCategory) => Promise<void>;
}) {
  const { t, language } = useI18n();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [icon, setIcon] = useState<CategoryIcon>(category?.icon || "folder");
  const [pending, setPending] = useState<Record<string, unknown> | null>(null);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    const payload = {
      ...data,
      parent_id: data.parent_id || null,
      description: category?.description || "",
      description_ru: category?.description_ru || "",
      icon,
      archived: category?.archived || false,
      expected_version: category?.version,
    };
    setPending(payload);
  }
  async function persist() {
    if (!pending || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = category
        ? await request<BookCategory>(
            `/pricing/catalog/categories/${category.id}`,
            { method: "PUT", body: JSON.stringify(pending) },
          )
        : await post<BookCategory>("/pricing/catalog/categories", pending);
      await onSaved(result);
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
        title={t(
          category
            ? "Edit category"
            : parentId
              ? "Add subcategory"
              : "Add category",
        )}
        onClose={() => {
          if (!busy) onClose();
        }}
      >
        <form onSubmit={save}>
          <div className="modal-body form-grid">
            {error ? (
              <div className="span-all">
                <ErrorNotice>{error}</ErrorNotice>
              </div>
            ) : null}
            <Field label={t("Category name (EN)")}>
              <input
                name="name"
                defaultValue={category?.name}
                required
                maxLength={160}
              />
            </Field>
            <Field label={t("Category name (RU)")}>
              <input
                name="name_ru"
                defaultValue={category?.name_ru}
                maxLength={160}
              />
            </Field>
            {!category?.builtin ? (
              <Field label={t("Parent category")}>
                <Select
                  name="parent_id"
                  defaultValue={category?.parent_id || parentId || ""}
                >
                  <option value="">{t("Top-level category")}</option>
                  {orderedCategories(categories)
                    .filter(
                      (c) =>
                        (categoryAvailable(c, categories) ||
                          c.id === category?.parent_id) &&
                        !categoryTrail(c, categories).some(
                          (ancestor) => ancestor.id === category?.id,
                        ),
                    )
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {categoryLabel(c, categories, language, t)}
                      </option>
                    ))}
                </Select>
              </Field>
            ) : null}
            <CategoryIconPicker value={icon} onChange={setIcon} />
            <p className="form-hint span-all">
              {t(
                category?.builtin
                  ? "Renaming a category keeps its existing calculation rules and saved estimates."
                  : "A category groups catalogue items. It does not create a new calculator.",
              )}
            </p>
          </div>
          <footer className="modal-footer">
            <Button onClick={onClose} disabled={busy}>
              {t("Cancel")}
            </Button>
            <Button type="submit" variant="primary" busy={busy}>
              {t("Save category")}
            </Button>
          </footer>
        </form>
      </Modal>
      {pending ? (
        <Confirm
          title={t(
            category ? "Save category changes?" : "Create this category?",
          )}
          action={t("Confirm save")}
          variant="primary"
          busy={busy}
          onClose={() => setPending(null)}
          onConfirm={persist}
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
