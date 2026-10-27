import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Check, Plus } from "lucide-react";
import { request, post, money, errorMessage } from "../../lib/api";
import type { CalculatedItem } from "../../lib/types";
import {
  type BookData,
  type BookItem,
  categoryAvailable,
  categoryLabel,
  categoryTrail,
  orderedCategories,
  localized,
} from "../../lib/pricebook";
import { useI18n } from "../../lib/i18n";
import { Button, EmptyState, ErrorNotice, Field, Loading } from "../ui";
import Select from "../Select";

export default function CatalogPicker({
  onAdd,
  onClose,
  onCreate,
  initialItem = null,
}: {
  onAdd: (items: CalculatedItem[]) => Promise<void>;
  onClose: () => void;
  onCreate: (name: string, category?: string) => void;
  initialItem?: BookItem | null;
}) {
  const { t, language } = useI18n();
  const [search, setSearch] = useState(""),
    [category, setCategory] = useState("");
  const [selected, setSelected] = useState<BookItem | null>(initialItem),
    [quantity, setQuantity] = useState(initialItem?.default_quantity || "1");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const query = useQuery({
    queryKey: ["pricebook-catalog"],
    queryFn: () => request<BookData>("/pricing/catalog"),
  });
  const activeCategories = orderedCategories(
    query.data?.categories || [],
  ).filter((c) => categoryAvailable(c, query.data?.categories || []));
  const items = (query.data?.items || []).filter(
    (i) =>
      !i.archived &&
      activeCategories.some((c) => c.id === i.category_id) &&
      (!category ||
        categoryTrail(
          activeCategories.find((c) => c.id === i.category_id)!,
          activeCategories,
        ).some((c) => c.id === category)) &&
      `${i.name} ${i.name_ru} ${i.description} ${i.description_ru}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()),
  );
  async function add() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const item = await post<CalculatedItem>(
        `/pricing/catalog/items/${selected.id}/quote`,
        { quantity: selected.pricing_mode === "fixed" ? "1" : quantity },
      );
      await onAdd([item]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="modal-body book-picker">
        {error ? <ErrorNotice>{error}</ErrorNotice> : null}
        <div className="book-picker-filters">
          <label className="search-field">
            <Search size={16} />
            <input
              aria-label={t("Search catalogue items")}
              placeholder={t("Search catalogue items…")}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setSelected(null);
              }}
            />
          </label>
          <Select
            aria-label={t("Filter catalogue category")}
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setSelected(null);
            }}
          >
            <option value="">{t("All categories")}</option>
            {activeCategories.map((c) => (
              <option key={c.id} value={c.id}>
                {categoryLabel(c, query.data?.categories || [], language, t)}
              </option>
            ))}
          </Select>
        </div>
        {query.isLoading ? (
          <Loading />
        ) : query.error ? (
          <ErrorNotice retry={() => query.refetch()}>
            {errorMessage(query.error)}
          </ErrorNotice>
        ) : !items.length ? (
          <EmptyState title={t("No matching items")}>
            {t(
              "Create a new item here or in Price Book to use it in this estimate.",
            )}
          </EmptyState>
        ) : (
          <div
            className="book-picker-list"
            role="group"
            aria-label={t("Catalogue items")}
          >
            {items.map((item) => (
              <button
                type="button"
                key={item.id}
                aria-pressed={selected?.id === item.id}
                className="book-picker-item"
                onClick={() => {
                  setSelected(item);
                  setQuantity(item.default_quantity);
                  setError("");
                }}
              >
                <span>
                  <strong>{localized(item, language, t)}</strong>
                  <small>
                    {localized(
                      activeCategories.find((c) => c.id === item.category_id)!,
                      language,
                      t,
                    )}{" "}
                    · {t(item.unit)}
                  </small>
                </span>
                <strong>
                  {item.pricing_mode === "unpriced"
                    ? t("Price pending")
                    : money(item.unit_price)}
                </strong>
                {selected?.id === item.id ? (
                  <Check size={17} aria-hidden="true" />
                ) : null}
              </button>
            ))}
          </div>
        )}
        {selected ? (
          <div className="book-picker-selection">
            <div>
              <strong>{localized(selected, language, t)}</strong>
              <p>
                {language === "ru"
                  ? selected.description_ru || selected.description
                  : selected.description}
              </p>
            </div>
            <Field label={t("Quantity")}>
              <input
                type="number"
                min="0.01"
                max="999999"
                step="0.01"
                value={selected.pricing_mode === "fixed" ? "1" : quantity}
                disabled={selected.pricing_mode === "fixed"}
                onChange={(e) => setQuantity(e.target.value)}
              />
            </Field>
            <div className="book-picker-total">
              <small>{t("Total to add")}</small>
              <strong>
                {selected.pricing_mode === "unpriced"
                  ? t("Price pending")
                  : money(
                      Number(selected.unit_price) *
                        (selected.pricing_mode === "fixed"
                          ? 1
                          : Number(quantity)),
                    )}
              </strong>
            </div>
          </div>
        ) : null}
        <p className="form-hint">
          {t(
            "Catalogue items use a fixed total or quantity × rate. Automatic calculators keep their own formulas.",
          )}
        </p>
      </div>
      <footer className="modal-footer">
        <Button
          className="book-picker-create"
          disabled={!query.data || busy}
          onClick={() => onCreate(search, category || selected?.category_id)}
        >
          <Plus size={16} aria-hidden="true" />
          {t("Add new Price Book item")}
        </Button>
        <Button onClick={onClose}>{t("Cancel")}</Button>
        <Button
          variant="primary"
          busy={busy}
          disabled={!selected || !Number(quantity) || Number(quantity) < 0.01}
          onClick={add}
        >
          {t("Add item to zone")}
        </Button>
      </footer>
    </>
  );
}
