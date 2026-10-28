import { useState, type FormEvent } from "react";
import type { JsonValue, PricingConfig } from "../../lib/types";
import { useI18n } from "../../lib/i18n";
import { Button, Field, Modal, ErrorNotice } from "../ui";
import Select from "../Select";

export type RateGroup = { path: string[]; title: string };
export const supportedGroup = (path: string[]) => {
  const key = path.join(".");
  return (
    [
      "wall.base_rates",
      "wall.addons_sf",
      "wall.addons_fixed",
      "cabinet.types",
      "cabinet.addons_lf",
      "cabinet.glass_doors",
      "mirror.types",
      "materials",
      "services",
      "colors",
      "quick_estimate.buildout_tiers",
    ].includes(key) ||
    (path[0] === "colors" && path.at(-1) === "options")
  );
};
export default function RateEntryForm({
  group,
  config,
  onChange,
  onClose,
}: {
  group: RateGroup;
  config: PricingConfig;
  onChange: (path: string[], value: JsonValue) => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [error, setError] = useState("");
  const key = group.path.join(".");
  const color = group.path[0] === "colors";
  const tier = key === "quick_estimate.buildout_tiers";
  const unit =
    key.startsWith("cabinet.") && key !== "cabinet.glass_doors"
      ? "$/LF"
      : key === "wall.base_rates" ||
          key === "wall.addons_sf" ||
          key === "mirror.types" ||
          key === "materials"
        ? "$/SF"
        : "$";
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = Object.fromEntries(new FormData(event.currentTarget));
    const label = String(f.label || "").trim();
    if (!label && !tier) return;
    const label_ru = String(f.label_ru || "").trim();
    const amount = Number(f.amount || 0);
    if (!Number.isFinite(amount) || amount < 0) return;
    const id = "custom_" + crypto.randomUUID().replaceAll("-", "");
    let current: JsonValue = config;
    for (const part of group.path)
      current = (current as Record<string, JsonValue>)[part];
    if (color) {
      onChange(group.path, [
        ...(Array.isArray(current) ? current : []),
        ...(key === "colors"
          ? [{ group: label, options: [String(f.option || label)] }]
          : [label]),
      ]);
    } else if (tier) {
      const max = Number(f.max_ft);
      const tiers = (Array.isArray(current) ? current : []) as {
        max_ft: number;
        price: number;
      }[];
      if (tiers.some((v) => v.max_ft === max)) {
        setError(t("A tier with this width already exists."));
        return;
      }
      onChange(
        group.path,
        [...tiers, { max_ft: max, price: amount }].sort(
          (a, b) => a.max_ft - b.max_ft,
        ),
      );
    } else {
      let value: JsonValue = { label, label_ru, price: amount };
      if (key === "wall.base_rates") {
        value = amount;
        onChange(["_rate_labels"], {
          ...((config._rate_labels || {}) as Record<string, JsonValue>),
          [group.path.concat(id).join(".")]: { label, label_ru },
        });
      } else if (key === "cabinet.types")
        value = { label, label_ru, base_rate: amount };
      else if (key === "mirror.types")
        value = { label, label_ru, rate: amount };
      else if (key === "services")
        value = {
          label,
          label_ru,
          default_price: amount,
          unit: String(f.unit || "Fixed"),
        };
      else if (key === "materials") {
        value = {
          label,
          label_ru,
          group: "Custom materials",
          tier: amount ? "premium" : "base",
          price_adder: amount,
          addon_key: amount ? id : null,
        };
        if (amount) {
          const wall = config.wall as Record<string, JsonValue>;
          onChange(["wall", "addons_sf"], {
            ...(wall.addons_sf as Record<string, JsonValue>),
            [id]: { label, label_ru, price: amount, describable: false },
          });
        }
      } else if (key.endsWith("addons_sf") || key.endsWith("addons_lf"))
        value = {
          label,
          label_ru,
          price: amount,
          describable: f.describable === "on",
        };
      onChange(group.path, {
        ...((current || {}) as Record<string, JsonValue>),
        [id]: value,
      });
    }
    onClose();
  }
  return (
    <Modal title={t("Add rate: {0}", t(group.title))} onClose={onClose}>
      <form onSubmit={save}>
        <div className="modal-body form-grid">
          {error ? (
            <div className="span-all">
              <ErrorNotice>{error}</ErrorNotice>
            </div>
          ) : null}
          {!tier ? (
            <>
              <Field label={t(color ? "Name (EN)" : "Rate name (EN)")}>
                <input name="label" required maxLength={160} />
              </Field>
              {!color ? (
                <Field label={t("Name (RU)")}>
                  <input name="label_ru" maxLength={160} />
                </Field>
              ) : null}
            </>
          ) : (
            <Field label={t("Maximum width (ft)")}>
              <input
                type="number"
                name="max_ft"
                min="0.01"
                max="999999"
                step="0.01"
                required
              />
            </Field>
          )}
          {key === "colors" ? (
            <Field label={t("First finish (EN)")}>
              <input name="option" maxLength={160} required />
            </Field>
          ) : null}
          {!color ? (
            <Field label={t("Price ({0})", unit)}>
              <input
                type="number"
                name="amount"
                min="0"
                max="9999999999.99"
                step="0.01"
                required
              />
            </Field>
          ) : null}
          {key === "services" ? (
            <Field label={t("Unit")}>
              <Select name="unit">
                {["Fixed", "ea", "HR", "SF", "LF"].map((u) => (
                  <option key={u} value={u}>
                    {t(u)}
                  </option>
                ))}
              </Select>
            </Field>
          ) : null}
          {key.endsWith("addons_lf") ? (
            <label className="check-label span-all">
              <input type="checkbox" name="describable" />
              <span>{t("Show add-on separately")}</span>
            </label>
          ) : null}
          <p className="form-hint span-all">
            {t(
              "This adds a draft entry. Click Save rates to confirm and publish it to the shared Price Book.",
            )}
          </p>
        </div>
        <footer className="modal-footer">
          <Button onClick={onClose}>{t("Cancel")}</Button>
          <Button type="submit" variant="primary">
            {t("Add to draft")}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}
