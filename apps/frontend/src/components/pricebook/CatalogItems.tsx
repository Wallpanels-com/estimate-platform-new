import { useState } from "react";
import { Archive, ArchiveRestore, Pencil, Search, Trash2 } from "lucide-react";
import { money } from "../../lib/api";
import { localized, itemKindLabel, type BookItem } from "../../lib/pricebook";
import { useI18n } from "../../lib/i18n";
import { Button, EmptyState } from "../ui";

export default function CatalogItems({
  items,
  showArchived,
  onEdit,
  onArchive,
  onRestore,
  onDelete,
  disabled = false,
}: {
  items: BookItem[];
  showArchived: boolean;
  onEdit: (i: BookItem) => void;
  onArchive: (i: BookItem) => void;
  onRestore: (i: BookItem) => void;
  onDelete: (i: BookItem) => void;
  disabled?: boolean;
}) {
  const { t, language } = useI18n();
  const [search, setSearch] = useState("");
  const visible = items.filter(
    (i) =>
      (showArchived || !i.archived) &&
      `${i.name} ${i.name_ru} ${i.description} ${i.description_ru}`
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()),
  );
  return (
    <div className="book-catalogue">
      <label className="search-field">
        <Search size={17} />
        <input
          aria-label={t("Search catalogue items")}
          placeholder={t("Search catalogue items…")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>
      {!visible.length ? (
        <EmptyState
          title={t(search ? "No matching items" : "No catalogue items yet")}
        >
          {t(
            "Add a work item, material or service to make it available in Estimate Builder.",
          )}
        </EmptyState>
      ) : (
        <div className="book-item-list">
          <div className="book-item-table-head" aria-hidden="true">
            <span>{t("Name / description")}</span>
            <span>{t("Unit")}</span>
            <span>{t("Price")}</span>
            <span>{t("Actions")}</span>
          </div>
          {visible.map((item) => (
            <article
              className={`book-item-row ${item.archived ? "book-archived" : ""}`}
              key={item.id}
            >
              <div className="book-item-name">
                <strong>{localized(item, language, t)}</strong>
                <small>
                  {t(itemKindLabel[item.kind])}
                  {item.archived ? ` · ${t("Archived")}` : ""}
                </small>
                {(
                  language === "ru"
                    ? item.description_ru || item.description
                    : item.description
                ) ? (
                  <p>
                    {language === "ru"
                      ? item.description_ru || item.description
                      : item.description}
                  </p>
                ) : null}
              </div>
              <span className="book-item-unit">{t(item.unit)}</span>
              <strong className="book-item-price">
                {item.pricing_mode === "unpriced"
                  ? t("Price pending")
                  : money(item.unit_price)}
              </strong>
              <div className="book-item-actions">
                {item.archived ? (
                  <>
                    <Button
                      variant="ghost"
                      aria-label={t(
                        "Restore {0}",
                        localized(item, language, t),
                      )}
                      title={t("Restore")}
                      onClick={() => onRestore(item)}
                      disabled={disabled}
                    >
                      <ArchiveRestore size={17} />
                    </Button>
                    <Button
                      variant="ghost"
                      aria-label={t(
                        "Delete permanently: {0}",
                        localized(item, language, t),
                      )}
                      title={t("Delete permanently")}
                      onClick={() => onDelete(item)}
                      disabled={disabled}
                    >
                      <Trash2 size={17} />
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      variant="ghost"
                      aria-label={t("Edit {0}", localized(item, language, t))}
                      title={t("Edit item")}
                      onClick={() => onEdit(item)}
                      disabled={disabled}
                    >
                      <Pencil size={17} />
                    </Button>
                    <Button
                      variant="ghost"
                      aria-label={t(
                        "Archive {0}",
                        localized(item, language, t),
                      )}
                      title={t("Archive")}
                      onClick={() => onArchive(item)}
                      disabled={disabled}
                    >
                      <Archive size={17} />
                    </Button>
                  </>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
