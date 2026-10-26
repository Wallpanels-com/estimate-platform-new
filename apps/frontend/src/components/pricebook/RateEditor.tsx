import { Coins, Settings2, Layers3 } from "lucide-react";
import type { JsonValue, PricingConfig } from "../../lib/types";
import { useI18n } from "../../lib/i18n";
import { Field } from "../ui";
import Select from "../Select";

type Change = (path: string[], value: JsonValue) => void;
const isObject = (value: JsonValue): value is Record<string, JsonValue> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const labels: Record<string, string> = {
  addons_sf: "Per-square-foot upgrades",
  addons_lf: "Per-linear-foot upgrades",
  addons_fixed: "Fixed-price additions",
  describable: "Show add-on separately",
  addon_key: "Linked price upgrade",
  price_adder: "Added rate",
  base_rates: "Base rates",
  glass_doors: "Glass doors",
  range_pct: "Range (%)",
  minimum: "Installation fee",
  base_rate: "Base rate",
  base_rate_budget: "Budget base rate",
  types: "Furniture types",
  rooms: "Room templates",
  fixed_items: "Fixed items",
  buildout_tiers: "Wall build-out tiers",
  mirror_installation: "Mirror installation",
  wall_rate: "Wall rate",
  mirror_rate: "Mirror rate",
  rate_small: "Small mirror rate",
  rate_large: "Large mirror rate",
  threshold_sf: "Area threshold (SF)",
  max_ft: "Maximum width (ft)",
  default_price: "Default price",
  items: "Work item keys",
  options: "Option keys",
  group: "Group",
  tier: "Material tier",
};
const human = (key: string) =>
  labels[key] || key.replace(/_/g, " ").replace(/^./, (s) => s.toUpperCase());
function unitFor(path: string[]) {
  const key = path.at(-1)!;
  if (key.endsWith("_pct")) return "%";
  if (key === "threshold_sf") return "SF";
  if (key === "max_ft") return "ft";
  if (
    [
      "price",
      "rate",
      "price_adder",
      "base_rate",
      "base_rate_budget",
      "wall_rate",
      "mirror_rate",
      "rate_small",
      "rate_large",
      "default_price",
      "minimum",
      "large",
      "medium",
      "small",
    ].includes(key)
  ) {
    if (
      path.includes("addons_sf") ||
      path.includes("materials") ||
      path.includes("base_rates") ||
      ["wall_rate", "mirror_rate", "rate_small", "rate_large"].includes(key) ||
      (path[0] === "mirror" && key === "rate")
    )
      return "$/SF";
    if (path[0] === "cabinet" && !path.includes("glass_doors")) return "$/LF";
    return "$";
  }
  return "";
}
function Scalar({
  value,
  path,
  onChange,
  upgrades,
}: {
  value: JsonValue;
  path: string[];
  onChange: Change;
  upgrades: Record<string, JsonValue>;
}) {
  const { t } = useI18n();
  const key = path.at(-1)!;
  const caption = /^\d+$/.test(key)
    ? t("Entry {0}", Number(key) + 1)
    : t(human(key));
  const accessible = path
    .map(human)
    .map((key) => t(key))
    .join(" / ");
  if (typeof value === "boolean")
    return (
      <label className="check-label rate-checkbox">
        <input
          type="checkbox"
          aria-label={accessible}
          checked={value}
          onChange={(e) => onChange(path, e.target.checked)}
        />
        <span>{caption}</span>
      </label>
    );
  if (key === "addon_key")
    return (
      <Field label={caption}>
        <Select
          aria-label={accessible}
          value={String(value ?? "")}
          onChange={(e) => onChange(path, e.target.value || null)}
        >
          <option value="">{t("No price upgrade")}</option>
          {Object.entries(upgrades).map(([k, v]) => (
            <option key={k} value={k}>
              {t(isObject(v) ? String(v.label) : k)}
            </option>
          ))}
        </Select>
      </Field>
    );
  if (key === "unit" || key === "tier") {
    const options =
      key === "unit"
        ? ["SF", "LF", "Fixed", "HR", "ea"]
        : ["base", "premium", "very_premium"];
    return (
      <Field label={caption}>
        <Select
          aria-label={accessible}
          value={String(value)}
          onChange={(e) => onChange(path, e.target.value)}
        >
          {options.map((v) => (
            <option key={v} value={v}>
              {t(v)}
            </option>
          ))}
        </Select>
      </Field>
    );
  }
  return (
    <Field label={caption}>
      {typeof value === "number" ? (
        <div className="rate-amount">
          <input
            type="number"
            aria-label={accessible}
            min="0"
            step="0.01"
            value={value}
            onChange={(e) =>
              onChange(path, e.target.value === "" ? 0 : Number(e.target.value))
            }
          />
          {unitFor(path) ? <span>{unitFor(path)}</span> : null}
        </div>
      ) : (
        <input
          aria-label={accessible}
          value={value == null ? "" : String(value)}
          onChange={(e) => onChange(path, e.target.value || null)}
        />
      )}
    </Field>
  );
}
function Branch({
  value,
  path,
  onChange,
  upgrades,
}: {
  value: JsonValue;
  path: string[];
  onChange: Change;
  upgrades: Record<string, JsonValue>;
}) {
  const { t } = useI18n();
  if (isObject(value) && typeof value.label === "string") {
    const amountKey = [
      "price",
      "base_rate",
      "default_price",
      "price_adder",
    ].find((k) => typeof value[k] === "number");
    const extra = Object.keys(value).filter(
      (k) => k !== "label" && k !== amountKey,
    );
    return (
      <div className="rate-entry">
        <div className="rate-row-core">
          <Field label={t(value.label)}>
            <input
              aria-label={t("Estimate name (EN): {0}", value.label)}
              value={value.label}
              onChange={(e) => onChange([...path, "label"], e.target.value)}
              required
            />
          </Field>
          {amountKey ? (
            <Scalar
              value={value[amountKey]}
              path={[...path, amountKey]}
              onChange={onChange}
              upgrades={upgrades}
            />
          ) : null}
          {extra.length ? (
            <details className="rate-parameters">
              <summary>
                <Settings2 size={15} />
                {t("Parameters")}
              </summary>
              <div className="rate-parameter-grid">
                {extra.map((key) => (
                  <Branch
                    key={key}
                    value={value[key]}
                    path={[...path, key]}
                    onChange={onChange}
                    upgrades={upgrades}
                  />
                ))}
              </div>
            </details>
          ) : null}
        </div>
      </div>
    );
  }
  if (Array.isArray(value))
    return (
      <div className="rate-list">
        {value.map((entry, index) => (
          <Branch
            key={index}
            value={entry}
            path={[...path, String(index)]}
            onChange={onChange}
            upgrades={upgrades}
          />
        ))}
      </div>
    );
  if (isObject(value)) {
    const entries = Object.entries(value);
    const simple = entries.every(([, v]) => !isObject(v) && !Array.isArray(v));
    return (
      <div className={simple ? "rate-grid" : "rate-list"}>
        {entries.map(([key, entry]) => (
          <Branch
            key={key}
            value={entry}
            path={[...path, key]}
            onChange={onChange}
            upgrades={upgrades}
          />
        ))}
      </div>
    );
  }
  return (
    <Scalar value={value} path={path} onChange={onChange} upgrades={upgrades} />
  );
}
export default function RateEditor({
  config,
  categoryId,
  onChange,
}: {
  config: PricingConfig;
  categoryId: string;
  onChange: Change;
}) {
  const { t } = useI18n();
  const current = config[categoryId];
  const wall = config.wall;
  const upgrades =
    isObject(wall) && isObject(wall.addons_sf) ? wall.addons_sf : {};
  if (categoryId === "colors" && Array.isArray(current))
    return (
      <div className="rate-sections">
        {current.map((group, index) =>
          isObject(group) ? (
            <section className="rate-section" key={index}>
              <header>
                <Layers3 size={17} />
                <h3>{t(String(group.group))}</h3>
              </header>
              <div className="rate-section-body rate-grid">
                <Scalar
                  value={group.group}
                  path={[categoryId, String(index), "group"]}
                  onChange={onChange}
                  upgrades={upgrades}
                />
                {Array.isArray(group.options)
                  ? group.options.map((v, i) => (
                      <Scalar
                        key={i}
                        value={v}
                        path={[categoryId, String(index), "options", String(i)]}
                        onChange={onChange}
                        upgrades={upgrades}
                      />
                    ))
                  : null}
              </div>
            </section>
          ) : null,
        )}
      </div>
    );
  if (!isObject(current)) return null;
  const simple = Object.entries(current).filter(
    ([, v]) => !isObject(v) && !Array.isArray(v),
  );
  const groups = Object.entries(current).filter(
    ([, v]) => isObject(v) || Array.isArray(v),
  );
  if (
    groups.length &&
    groups.every(([, v]) => isObject(v) && typeof v.label === "string")
  )
    return (
      <div className="rate-sections">
        <section className="rate-section">
          <header>
            <Layers3 size={17} />
            <h3>
              {t(
                categoryId === "services"
                  ? "Service templates"
                  : "Material library",
              )}
            </h3>
          </header>
          <div className="rate-section-body">
            <Branch
              value={current}
              path={[categoryId]}
              onChange={onChange}
              upgrades={upgrades}
            />
          </div>
        </section>
      </div>
    );
  return (
    <div className="rate-sections">
      {simple.length ? (
        <section className="rate-section">
          <header>
            <Coins size={17} />
            <h3>{t("Base rates")}</h3>
          </header>
          <div className="rate-section-body rate-grid">
            {simple.map(([key, v]) => (
              <Scalar
                key={key}
                value={v}
                path={[categoryId, key]}
                onChange={onChange}
                upgrades={upgrades}
              />
            ))}
          </div>
        </section>
      ) : null}
      {groups.map(([key, value]) => (
        <section className="rate-section" key={key}>
          <header>
            <Layers3 size={17} />
            <h3>{t(human(key))}</h3>
          </header>
          <div className="rate-section-body">
            <Branch
              value={value}
              path={[categoryId, key]}
              onChange={onChange}
              upgrades={upgrades}
            />
          </div>
        </section>
      ))}
      <p className="form-hint">
        {t(
          "Catalogue names stay in English for estimate outputs. Editing rates does not reprice saved estimates.",
        )}
      </p>
    </div>
  );
}
