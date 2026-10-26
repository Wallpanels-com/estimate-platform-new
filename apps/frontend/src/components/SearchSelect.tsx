import { useContext, useId, useState, type RefObject } from "react";
import { ChevronDown, Plus } from "lucide-react";
import { FieldContext } from "../lib/fieldContext";
import { useI18n } from "../lib/i18n";
import { ChoiceMenu, useChoices, type Choice } from "./Select";

const CREATE = "create:pricebook-item";

/** Search only selects saved choices; free text is carried into the item editor. */
export default function SearchSelect({
  options,
  value,
  onSelect,
  onCreate,
  disabled = false,
}: {
  options: Choice[];
  value: string;
  onSelect: (value: string) => void;
  onCreate: (name: string) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const field = useContext(FieldContext);
  const uid = useId();
  const [query, setQuery] = useState<string | null>(null);
  const items = options.filter((option) =>
    `${option.label} ${option.keywords || ""}`
      .toLocaleLowerCase()
      .includes((query || "").trim().toLocaleLowerCase()),
  );
  items.push({
    value: CREATE,
    label: t("Add new Price Book item"),
    create: true,
  });
  const c = useChoices(items, value, (chosen) => {
    if (chosen === CREATE) onCreate((query || "").trim());
    else onSelect(chosen);
    setQuery(null);
  });
  return (
    <div className="search-select">
      <div className="choice editable-choice">
        <input
          ref={c.trigger as RefObject<HTMLInputElement>}
          id={field?.id || uid}
          aria-labelledby={field?.labelId}
          aria-describedby={field?.hintId}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={c.open}
          aria-controls={c.id}
          aria-activedescendant={
            c.open && c.active >= 0 && items[c.active]
              ? `${c.id}-${c.active}`
              : undefined
          }
          autoComplete="off"
          placeholder={t("Search calculators or Price Book items…")}
          disabled={disabled}
          value={
            query ??
            options.find((option) => option.value === value)?.label ??
            ""
          }
          onFocus={() => {
            setQuery("");
            if (!c.open) c.show();
          }}
          onClick={() => {
            if (!c.open) c.show();
          }}
          onBlur={() => {
            c.close();
            setQuery(null);
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            c.setActive(0);
            if (!c.open) c.show(0);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") setQuery(null);
            c.onKeyDown(event, true);
          }}
        />
        <button
          type="button"
          className="choice-toggle"
          tabIndex={-1}
          disabled={disabled}
          aria-label={t("Show options")}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => {
            setQuery(null);
            c.open ? c.close() : c.show();
            c.trigger.current?.focus();
          }}
        >
          <ChevronDown size={16} aria-hidden="true" />
        </button>
        <ChoiceMenu
          controller={c}
          items={items}
          selected={value}
          labelId={field?.labelId}
        />
      </div>
      <button
        type="button"
        className="button secondary search-select-create"
        disabled={disabled}
        aria-label={t("Add new Price Book item")}
        title={t("Add new Price Book item")}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => {
          c.close();
          onCreate((query || "").trim());
          setQuery(null);
        }}
      >
        <Plus size={18} aria-hidden="true" />
      </button>
    </div>
  );
}
