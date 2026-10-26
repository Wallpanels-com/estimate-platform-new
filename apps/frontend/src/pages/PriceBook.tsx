import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArchiveRestore,
  Pencil,
  Plus,
  RotateCcw,
  Save,
  SlidersHorizontal,
  BookOpen,
} from "lucide-react";
import { request, post, errorMessage } from "../lib/api";
import type { JsonValue, PricingConfig } from "../lib/types";
import {
  type BookData,
  type BookItem,
  type BookCategory,
  categoryIcons,
  categoryBody,
  itemBody,
  localized,
} from "../lib/pricebook";
import { useI18n } from "../lib/i18n";
import {
  Button,
  Confirm,
  ErrorNotice,
  Loading,
  PageHeader,
  useNotice,
} from "../components/ui";
import CategoryForm from "../components/pricebook/CategoryForm";
import ItemForm from "../components/pricebook/ItemForm";
import CatalogItems from "../components/pricebook/CatalogItems";
import RateEditor from "../components/pricebook/RateEditor";

type ConfigResponse = {
  config: PricingConfig;
  is_default: boolean;
  revision: string;
};
export default function PriceBook() {
  const { t, language } = useI18n();
  const client = useQueryClient(),
    notify = useNotice();
  const [tab, setTab] = useState("wall"),
    [view, setView] = useState("rates");
  const [config, setConfig] = useState<PricingConfig | null>(null),
    [revision, setRevision] = useState("");
  const [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [reset, setReset] = useState(false),
    [showArchived, setShowArchived] = useState(false);
  const [categoryForm, setCategoryForm] = useState<BookCategory | "new" | null>(
      null,
    ),
    [itemForm, setItemForm] = useState<BookItem | "new" | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<
    | { kind: "category"; entry: BookCategory }
    | { kind: "item"; entry: BookItem }
    | null
  >(null);
  const query = useQuery({
    queryKey: ["pricing-config"],
    queryFn: () => request<ConfigResponse>("/pricing/config"),
  });
  const catalog = useQuery({
    queryKey: ["pricebook-catalog"],
    queryFn: () => request<BookData>("/pricing/catalog"),
  });
  useEffect(() => {
    if (query.data && !dirty) {
      setConfig(structuredClone(query.data.config));
      setRevision(query.data.revision);
    }
  }, [query.data, dirty]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const categories = catalog.data?.categories || [];
  const category = categories.find((c) => c.id === tab) || categories[0];
  const name = category ? localized(category, language, t) : "";
  const Icon = categoryIcons[category?.icon || "folder"];
  const items = (catalog.data?.items || []).filter(
    (i) => i.category_id === category?.id,
  );
  const activeCount = items.filter((i) => !i.archived).length;
  function select(c: BookCategory) {
    setTab(c.id);
    setView(c.builtin ? "rates" : "items");
  }
  function change(path: string[], value: JsonValue) {
    setConfig((previous) => {
      const next = structuredClone(previous!);
      let node: Record<string, JsonValue> | JsonValue[] = next;
      for (const key of path.slice(0, -1))
        node = (node as Record<string, JsonValue>)[key] as Record<
          string,
          JsonValue
        >;
      (node as Record<string, JsonValue>)[path.at(-1)!] = value;
      return next;
    });
    setDirty(true);
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await request<ConfigResponse>("/pricing/config", {
        method: "PUT",
        body: JSON.stringify({ config, expected_revision: revision }),
      });
      client.setQueryData(["pricing-config"], result);
      setConfig(structuredClone(result.config));
      setRevision(result.revision);
      setDirty(false);
      await client.invalidateQueries({ queryKey: ["pricing-schema"] });
      notify("Price book saved");
    } catch (err) {
      notify(errorMessage(err), true);
    } finally {
      setBusy(false);
    }
  }
  async function refreshCatalogue() {
    await client.invalidateQueries({ queryKey: ["pricebook-catalog"] });
  }
  async function archive(
    kind: "category" | "item",
    entry: BookCategory | BookItem,
    archived: boolean,
  ) {
    setBusy(true);
    try {
      const body =
        kind === "category"
          ? categoryBody(entry as BookCategory)
          : itemBody(entry as BookItem);
      await request(
        `/pricing/catalog/${kind === "category" ? "categories" : "items"}/${entry.id}`,
        { method: "PUT", body: JSON.stringify({ ...body, archived }) },
      );
      await refreshCatalogue();
      setArchiveTarget(null);
      if (kind === "category" && archived && !showArchived) {
        setTab("wall");
        setView("rates");
      }
      notify(archived ? "Entry archived" : "Entry restored");
    } catch (err) {
      notify(errorMessage(err), true);
    } finally {
      setBusy(false);
    }
  }
  async function resetDefaults() {
    setBusy(true);
    try {
      const result = await post<ConfigResponse>("/pricing/config/reset");
      client.setQueryData(["pricing-config"], result);
      setConfig(structuredClone(result.config));
      setRevision(result.revision);
      setDirty(false);
      await client.invalidateQueries({ queryKey: ["pricing-schema"] });
      setReset(false);
      notify("Default pricing restored");
    } catch (err) {
      notify(errorMessage(err), true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader
        title={t("Price book")}
        description={t(
          "Manage calculation rates and ready-to-use estimate items.",
        )}
        actions={
          <Button onClick={() => setReset(true)} disabled={busy || !config}>
            <RotateCcw size={16} />
            {t("Restore defaults")}
          </Button>
        }
      />
      {query.isLoading || catalog.isLoading ? (
        <Loading />
      ) : query.error || catalog.error || !config || !category ? (
        <ErrorNotice
          retry={() => {
            query.refetch();
            catalog.refetch();
          }}
        >
          {errorMessage(query.error || catalog.error)}
        </ErrorNotice>
      ) : (
        <div className="book-layout">
          <aside className="book-navigation">
            <nav aria-label={t("Price categories")}>
              {categories
                .filter((c) => showArchived || !c.archived)
                .map((c) => {
                  const CategoryIcon = categoryIcons[c.icon];
                  return (
                    <button
                      type="button"
                      key={c.id}
                      aria-current={category.id === c.id ? "page" : undefined}
                      className={c.archived ? "book-archived" : ""}
                      onClick={() => select(c)}
                    >
                      <CategoryIcon size={18} aria-hidden="true" />
                      <span>{localized(c, language, t)}</span>
                      {c.archived ? (
                        <Archive size={14} aria-hidden="true" />
                      ) : null}
                    </button>
                  );
                })}
              <Button
                className="book-add-category"
                onClick={() => setCategoryForm("new")}
              >
                <Plus size={17} />
                {t("Add category")}
              </Button>
            </nav>
            <label className="book-archive-toggle">
              <input
                type="checkbox"
                checked={showArchived}
                onChange={(e) => {
                  setShowArchived(e.target.checked);
                  if (!e.target.checked && category.archived) {
                    setTab("wall");
                    setView("rates");
                  }
                }}
              />
              <span>{t("Show archived")}</span>
            </label>
          </aside>
          <div className="book-main">
            <header className="book-category-header">
              <div className="book-category-title">
                <Icon size={24} aria-hidden="true" />
                <div>
                  <h2>{name}</h2>
                  <p>
                    {(language === "ru"
                      ? category.description_ru || category.description
                      : category.description) ||
                      t(
                        category.calculator_id
                          ? "Existing calculator rules and catalogue items."
                          : category.id === "quick_estimate"
                            ? "Separate room-template settings. Existing Quick formulas are preserved."
                            : "Catalogue entries and their applicable settings.",
                      )}
                  </p>
                </div>
              </div>
              <div className="book-category-actions">
                <Button
                  variant="ghost"
                  aria-label={t("Edit category")}
                  title={t("Edit category")}
                  onClick={() => setCategoryForm(category)}
                >
                  <Pencil size={17} />
                </Button>
                {!category.builtin ? (
                  <Button
                    variant="ghost"
                    aria-label={t(
                      category.archived
                        ? "Restore category"
                        : "Archive category",
                    )}
                    title={t(
                      category.archived
                        ? "Restore category"
                        : "Archive category",
                    )}
                    disabled={busy}
                    onClick={() =>
                      category.archived
                        ? archive("category", category, false)
                        : setArchiveTarget({
                            kind: "category",
                            entry: category,
                          })
                    }
                  >
                    {category.archived ? (
                      <ArchiveRestore size={17} />
                    ) : (
                      <Archive size={17} />
                    )}
                  </Button>
                ) : null}
                <Button
                  variant="primary"
                  onClick={() => setItemForm("new")}
                  disabled={category.archived}
                >
                  <Plus size={16} />
                  {t("Add item")}
                </Button>
              </div>
            </header>
            {category.archived ? (
              <p className="book-context-note">
                {t(
                  "This category is archived. Restore it to use its items in estimates.",
                )}
              </p>
            ) : null}
            {category.builtin ? (
              <div
                className="book-view-tabs"
                role="group"
                aria-label={t("Price Book view")}
              >
                <button
                  type="button"
                  aria-pressed={view === "rates"}
                  onClick={() => setView("rates")}
                >
                  <SlidersHorizontal size={16} />
                  {t("Rates & parameters")}
                </button>
                <button
                  type="button"
                  aria-pressed={view === "items"}
                  onClick={() => setView("items")}
                >
                  <BookOpen size={16} />
                  {t("Estimate items")}
                  <span>{activeCount}</span>
                </button>
              </div>
            ) : null}
            {category.builtin && view === "rates" ? (
              <form onSubmit={save} className="book-rate-form">
                {category.id === "quick_estimate" ? (
                  <p className="book-context-note">
                    {t(
                      "Quick Estimate currently uses separate legacy template rates. These settings do not update all room-template calculations.",
                    )}
                  </p>
                ) : null}
                <RateEditor
                  config={config}
                  categoryId={category.id}
                  onChange={change}
                />
                <footer className="book-save-bar">
                  <span role="status">
                    {t(
                      dirty
                        ? "You have unsaved changes."
                        : "Your price book is up to date.",
                    )}
                  </span>
                  <Button
                    type="submit"
                    variant="primary"
                    busy={busy}
                    disabled={!dirty}
                  >
                    <Save size={16} />
                    {t("Save rates")}
                  </Button>
                </footer>
              </form>
            ) : (
              <>
                <p className="book-context-note">
                  {t(
                    "Available in Estimate Builder → Add items → Price Book. Saved estimates keep a copy of the selected name and price.",
                  )}
                </p>
                <CatalogItems
                  items={items}
                  showArchived={showArchived}
                  onEdit={setItemForm}
                  onArchive={(item) =>
                    setArchiveTarget({ kind: "item", entry: item })
                  }
                  onRestore={(item) => archive("item", item, false)}
                  disabled={busy || category.archived}
                />
              </>
            )}
          </div>
        </div>
      )}
      {categoryForm ? (
        <CategoryForm
          category={categoryForm === "new" ? undefined : categoryForm}
          onClose={() => setCategoryForm(null)}
          onSaved={async (c) => {
            await refreshCatalogue();
            select(c);
            notify("Category saved");
          }}
        />
      ) : null}
      {itemForm && category ? (
        <ItemForm
          item={itemForm === "new" ? undefined : itemForm}
          categories={categories}
          categoryId={category.id}
          onClose={() => setItemForm(null)}
          onSaved={async () => {
            await refreshCatalogue();
            setView("items");
            notify("Catalogue item saved");
          }}
        />
      ) : null}
      {archiveTarget ? (
        <Confirm
          title={t(
            archiveTarget.kind === "category"
              ? "Archive this category?"
              : "Archive this item?",
          )}
          action={t("Archive")}
          busy={busy}
          onClose={() => setArchiveTarget(null)}
          onConfirm={() =>
            archive(archiveTarget.kind, archiveTarget.entry, true)
          }
        >
          {t(
            "Archived entries are hidden from new estimates. Existing estimates are unchanged, and you can restore this entry later.",
          )}
        </Confirm>
      ) : null}
      {reset ? (
        <Confirm
          title={t("Restore default pricing?")}
          action={t("Restore defaults")}
          busy={busy}
          onClose={() => setReset(false)}
          onConfirm={resetDefaults}
        >
          {t(
            "Original calculation rates will be restored. Your custom categories, catalogue items and saved estimates will be kept.",
          )}
        </Confirm>
      ) : null}
    </>
  );
}
