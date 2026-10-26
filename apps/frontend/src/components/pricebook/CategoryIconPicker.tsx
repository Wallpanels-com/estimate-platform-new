import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown, Search, X } from "lucide-react";
import {
  categoryIconIds,
  categoryIconLibrary,
  categoryIcons,
  type CategoryIcon,
} from "../../lib/category-icons";
import { useI18n } from "../../lib/i18n";

export default function CategoryIconPicker({
  value,
  onChange,
}: {
  value: CategoryIcon;
  onChange: (icon: CategoryIcon) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const trigger = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const id = useId();
  const Icon = categoryIcons[value];
  const query = search.trim().toLocaleLowerCase();
  const matches = categoryIconIds.filter((key) => {
    const item = categoryIconLibrary[key];
    return `${item.label} ${t(item.label)} ${item.group} ${t(item.group)} ${item.keywords}`
      .toLocaleLowerCase()
      .includes(query);
  });
  const groups = [
    ...new Set(matches.map((key) => categoryIconLibrary[key].group)),
  ];
  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);
  function close() {
    setOpen(false);
    trigger.current?.focus();
  }
  return (
    <div className="category-icon-picker span-all">
      <div className="category-icon-selection">
        <button
          ref={trigger}
          type="button"
          className="category-icon-trigger"
          aria-label={t("Choose an icon")}
          aria-expanded={open}
          aria-controls={id}
          onClick={() => {
            setOpen(!open);
            setSearch("");
          }}
        >
          <Icon size={28} aria-hidden="true" />
          <ChevronDown size={14} aria-hidden="true" />
        </button>
        <div>
          <span>{t("Category icon")}</span>
          <strong>{t(categoryIconLibrary[value].label)}</strong>
          <small>{t("Click the icon to change it.")}</small>
        </div>
      </div>
      {open ? (
        <section
          id={id}
          className="category-icon-library"
          aria-label={t("Icon library")}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              close();
            }
          }}
        >
          <div className="category-icon-search">
            <label className="search-field">
              <Search size={16} aria-hidden="true" />
              <input
                ref={input}
                type="search"
                aria-label={t("Search icons")}
                placeholder={t("Search by name or purpose…")}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") event.preventDefault();
                }}
              />
            </label>
            <button
              type="button"
              className="category-icon-close"
              aria-label={t("Close icon library")}
              onClick={close}
            >
              <X size={17} aria-hidden="true" />
            </button>
          </div>
          <div className="category-icon-results">
            {groups.map((group) => (
              <div className="category-icon-group" key={group}>
                <h3>{t(group)}</h3>
                <div
                  className="category-icon-grid"
                  role="group"
                  aria-label={t(group)}
                >
                  {matches
                    .filter((key) => categoryIconLibrary[key].group === group)
                    .map((key) => {
                      const Glyph = categoryIcons[key];
                      return (
                        <button
                          key={key}
                          type="button"
                          aria-label={t(categoryIconLibrary[key].label)}
                          title={t(categoryIconLibrary[key].label)}
                          aria-pressed={value === key}
                          onClick={() => {
                            onChange(key);
                            close();
                          }}
                        >
                          <Glyph size={23} aria-hidden="true" />
                        </button>
                      );
                    })}
                </div>
              </div>
            ))}
            {!matches.length ? <p>{t("No matching icons")}</p> : null}
          </div>
          <div className="category-icon-count" role="status">
            {t("Icons: {0}", matches.length)}
          </div>
        </section>
      ) : null}
    </div>
  );
}
