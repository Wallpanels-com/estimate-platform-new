import { useEffect, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArchiveRestore,
  Pencil,
  Plus,
  Save,
  SlidersHorizontal,
  BookOpen,
  Trash2,
} from "lucide-react";
import { request, errorMessage } from "../lib/api";
import type { JsonValue, PricingConfig } from "../lib/types";
import {
  type BookData,
  type BookItem,
  type BookCategory,
  categoryIcons,
  categoryBody,
  itemBody,
  localized,
  categoryAvailable,
  categoryLabel,
  categoryTrail,
  orderedCategories,
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
import RateEntryForm, {
  supportedGroup,
  type RateGroup,
} from "../components/pricebook/RateEntryForm";
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
    [showArchived, setShowArchived] = useState(false),
    [confirmRates, setConfirmRates] = useState(false),
    [actionError, setActionError] = useState(""),
    [deleteTarget, setDeleteTarget] = useState<{
      kind: "category" | "item";
      entry: BookCategory | BookItem;
    } | null>(null);
  const [categoryForm, setCategoryForm] = useState<BookCategory | "new" | null>(
      null,
    ),
    [itemForm, setItemForm] = useState<BookItem | "new" | null>(null);
  const [rateGroup, setRateGroup] = useState<RateGroup | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<
    | { kind: "category"; entry: BookCategory; restore?: boolean }
    | { kind: "item"; entry: BookItem; restore?: boolean }
    | null
  >(null);
  const query = useQuery({
    queryKey: ["pricing-config"],
    refetchInterval: dirty || busy ? false : 8000,
    queryFn: () => request<ConfigResponse>("/pricing/config"),
  });
  const catalog = useQuery({
    queryKey: ["pricebook-catalog"],
    refetchInterval: busy || categoryForm || itemForm ? false : 8000,
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
  useEffect(() => {
    setActionError("");
  }, [confirmRates, archiveTarget, deleteTarget]);
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
    setConfirmRates(true);
  }
  async function persistRates() {
    if (busy) return;
    setBusy(true);
    setActionError("");
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
      await client.invalidateQueries({ queryKey: ["quick-pricing"] });
      notify("Price book saved");
      setConfirmRates(false);
    } catch (err) {
      setActionError(errorMessage(err));
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
    setActionError("");
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
      setActionError(errorMessage(err));
      notify(errorMessage(err), true);
    } finally {
      setBusy(false);
    }
  }
  async function permanentlyDelete() {
    if (!deleteTarget || busy) return;
    setBusy(true);
    setActionError("");
    try {
      await request(
        `/pricing/catalog/${deleteTarget.kind === "category" ? "categories" : "items"}/${deleteTarget.entry.id}?expected_version=${deleteTarget.entry.version}`,
        { method: "DELETE" },
      );
      await refreshCatalogue();
      if (deleteTarget.kind === "category") {
        setTab("wall");
        setView("rates");
      }
      setDeleteTarget(null);
      notify("Entry permanently deleted");
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader title={t("Price book")} />
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
              {orderedCategories(categories)
                .filter((c) => showArchived || categoryAvailable(c, categories))
                .map((c) => {
                  const CategoryIcon = categoryIcons[c.icon];
                  return (
                    <button
                      type="button"
                      key={c.id}
                      aria-current={category.id === c.id ? "page" : undefined}
                      className={`${!categoryAvailable(c, categories) ? "book-archived" : ""} ${c.parent_id ? "book-subcategory" : ""}`}
                      title={categoryLabel(c, categories, language, t)}
                      style={{
                        paddingInlineStart:
                          12 +
                          Math.min(categoryTrail(c, categories).length - 1, 4) *
                            16,
                      }}
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
                onClick={() => {
                  setCategoryForm("new");
                }}
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
                  {category.parent_id ? (
                    <p className="book-breadcrumb">
                      {categoryTrail(category, categories)
                        .slice(0, -1)
                        .map((c) => localized(c, language, t))
                        .join(" / ")}
                    </p>
                  ) : null}
                  <h2>{name}</h2>
                </div>
              </div>
              <div className="book-category-actions">
                {!category.archived ? (
                  <Button
                    variant="ghost"
                    aria-label={t("Edit category")}
                    title={t("Edit category")}
                    onClick={() => setCategoryForm(category)}
                  >
                    <Pencil size={17} />
                  </Button>
                ) : null}
                {!category.builtin ? (
                  <Button
                    variant={category.archived ? "secondary" : "ghost"}
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
                        ? setArchiveTarget({
                            kind: "category",
                            entry: category,
                            restore: true,
                          })
                        : setArchiveTarget({
                            kind: "category",
                            entry: category,
                          })
                    }
                  >
                    {category.archived ? (
                      <>
                        <ArchiveRestore size={17} />
                        {t("Restore")}
                      </>
                    ) : (
                      <Archive size={17} />
                    )}
                  </Button>
                ) : null}
                {category.archived && !category.builtin ? (
                  <Button
                    variant="danger"
                    onClick={() =>
                      setDeleteTarget({ kind: "category", entry: category })
                    }
                  >
                    <Trash2 size={16} />
                    {t("Delete permanently")}
                  </Button>
                ) : null}
                {!category.archived ? (
                  <Button
                    variant="primary"
                    onClick={() => setItemForm("new")}
                    disabled={!categoryAvailable(category, categories)}
                  >
                    <Plus size={16} />
                    {t("Add item")}
                  </Button>
                ) : null}
              </div>
            </header>
            {!categoryAvailable(category, categories) ? (
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
                      "Quick Estimate keeps its own room-template formulas and uses the saved rates below.",
                    )}
                  </p>
                ) : null}
                <RateEditor
                  config={config}
                  categoryId={category.id}
                  onChange={change}
                  onAdd={(path, title) => {
                    if (supportedGroup(path)) setRateGroup({ path, title });
                    else {
                      setItemForm("new");
                      notify(
                        "This group uses a fixed formula. Add a catalogue item for other work.",
                      );
                    }
                  }}
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
                  items={
                    category.archived
                      ? items.map((item) => ({ ...item, archived: true }))
                      : items
                  }
                  showArchived={showArchived}
                  onEdit={setItemForm}
                  onArchive={(item) =>
                    setArchiveTarget({ kind: "item", entry: item })
                  }
                  onDelete={(item) =>
                    setDeleteTarget({ kind: "item", entry: item })
                  }
                  onRestore={(item) =>
                    setArchiveTarget({
                      kind: "item",
                      entry: item,
                      restore: true,
                    })
                  }
                  disabled={busy}
                />
              </>
            )}
          </div>
        </div>
      )}
      {rateGroup && config ? (
        <RateEntryForm
          group={rateGroup}
          config={config}
          onChange={change}
          onClose={() => setRateGroup(null)}
        />
      ) : null}
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
            archiveTarget.restore
              ? "Restore this entry?"
              : archiveTarget.kind === "category"
                ? "Archive this category?"
                : "Archive this item?",
          )}
          action={t(archiveTarget.restore ? "Restore" : "Archive")}
          variant={archiveTarget.restore ? "primary" : "danger"}
          error={actionError}
          busy={busy}
          onClose={() => setArchiveTarget(null)}
          onConfirm={() =>
            archive(
              archiveTarget.kind,
              archiveTarget.entry,
              !archiveTarget.restore,
            )
          }
        >
          <strong className="book-confirm-name">
            {localized(archiveTarget.entry, language, t)}
          </strong>
          {t(
            archiveTarget.restore
              ? "This entry will be available in new estimates again."
              : archiveTarget.kind === "category"
                ? "This category and its items will be hidden from new estimates. Existing estimates are unchanged. You can restore the category later."
                : "Archived entries are hidden from new estimates. Existing estimates are unchanged, and you can restore this entry later.",
          )}
        </Confirm>
      ) : null}
      {deleteTarget ? (
        <Confirm
          title={t("Permanently delete this entry?")}
          action={t("Delete permanently")}
          busy={busy}
          error={actionError}
          onClose={() => setDeleteTarget(null)}
          onConfirm={permanentlyDelete}
        >
          <strong className="book-confirm-name">
            {localized(deleteTarget.entry, language, t)}
          </strong>
          {t(
            deleteTarget.kind === "category"
              ? "This category and all its catalogue items will be permanently deleted. This cannot be undone. Saved estimates are unchanged."
              : "This catalogue item will be permanently deleted. This cannot be undone. Saved estimates are unchanged.",
          )}
        </Confirm>
      ) : null}
      {confirmRates ? (
        <Confirm
          title={t("Save pricing changes?")}
          action={t("Confirm save")}
          variant="primary"
          busy={busy}
          error={actionError}
          onClose={() => setConfirmRates(false)}
          onConfirm={persistRates}
        >
          {t(
            "Save all changed rates and parameters to the shared Price Book? All employees will use these values for new calculations. Saved estimates will not be repriced.",
          )}
        </Confirm>
      ) : null}
    </>
  );
}
