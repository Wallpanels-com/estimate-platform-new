import Select, { Combobox } from "./Select";
import CatalogPicker from "./pricebook/CatalogPicker";
import ItemForm from "./pricebook/ItemForm";
import SearchSelect from "./SearchSelect";
import {
  type BookData,
  type BookItem,
  categoryAvailable,
  localized,
} from "../lib/pricebook";
import { useI18n } from "../lib/i18n";
import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Field, Modal, ErrorNotice, Loading } from "./ui";
import { request, post, money, errorMessage } from "../lib/api";
import type { CalculatedItem, PricingSchema, Zone } from "../lib/types";
export default function AddItems({
  zone,
  onAdd,
  onClose,
  initial = "calculator",
}: {
  zone: Zone;
  onAdd: (items: CalculatedItem[]) => Promise<void>;
  onClose: () => void;
  initial?: "calculator" | "manual" | "services" | "catalog";
}) {
  const { t, language } = useI18n();
  const client = useQueryClient();
  const catalog = useQuery({
    queryKey: ["pricebook-catalog"],
    queryFn: () => request<BookData>("/pricing/catalog"),
  });
  const categories = (catalog.data?.categories || []).filter((c) =>
    categoryAvailable(c, catalog.data?.categories || []),
  );
  const catalogItems = (catalog.data?.items || []).filter(
    (i) => !i.archived && categories.some((c) => c.id === i.category_id),
  );
  const [selectedCatalog, setSelectedCatalog] = useState<BookItem | null>(null);
  const [createItem, setCreateItem] = useState<{
    name: string;
    category: string;
  } | null>(null);
  function openCreate(name: string, category = type) {
    setCreateItem({ name: name.slice(0, 200), category });
  }
  async function savedItem(item: BookItem) {
    client.setQueryData<BookData>(["pricebook-catalog"], (old) =>
      old
        ? {
            ...old,
            items: [...old.items.filter((i) => i.id !== item.id), item],
          }
        : old,
    );
    void client.invalidateQueries({ queryKey: ["pricebook-catalog"] });
    const quoted = await post<CalculatedItem>(
      `/pricing/catalog/items/${item.id}/quote`,
      { quantity: item.pricing_mode === "fixed" ? "1" : item.default_quantity },
    );
    await onAdd([quoted]);
    onClose();
  }

  const [tab, setTab] = useState(initial);
  const [type, setType] = useState(zone.zone_type);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{
    total: number;
    line_items: CalculatedItem[];
  } | null>(null);
  const [checked, setChecked] = useState<string[]>([]);
  const [fixed, setFixed] = useState<Record<string, number>>({});
  const schema = useQuery({
    queryKey: ["pricing-schema"],
    queryFn: () => request<PricingSchema>("/pricing/schema"),
  });
  const toggle = (key: string) => {
    setChecked((v) =>
      v.includes(key) ? v.filter((k) => k !== key) : [...v, key],
    );
    setResult(null);
  };
  async function calculate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError("");
    try {
      const options =
        type === "wall"
          ? {
              square_footage: Number(f.square_footage),
              addons_sf: checked,
              addons_fixed: Object.entries(fixed)
                .filter(([, qty]) => qty > 0)
                .map(([key, qty]) => ({ key, qty })),
              panel_name: f.panel_name || null,
              panel_color: f.panel_color || null,
              panel_coverage_pct: f.panel_coverage_pct
                ? Number(f.panel_coverage_pct)
                : null,
            }
          : type === "cabinet"
            ? {
                linear_footage: Number(f.linear_footage),
                cabinet_type: f.cabinet_type || null,
                budget: f.budget === "on",
                addons_lf: checked,
                glass_doors: Object.entries(fixed)
                  .filter(([, qty]) => qty > 0)
                  .map(([type, qty]) => ({ type, qty })),
              }
            : { square_footage: Number(f.square_footage) };
      setResult(await post(`/pricing/calc/${type}`, options));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  async function add(items: CalculatedItem[]) {
    setBusy(true);
    setError("");
    try {
      await onAdd(items);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  async function manual(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    const quantity = f.quantity === "" ? null : Number(f.quantity);
    const rate = f.unit_price === "" ? null : Number(f.unit_price);
    await add([
      {
        name: String(f.name),
        description: String(f.description),
        section: String(f.section || "General"),
        calc_type: String(f.calc_type),
        quantity,
        unit: f.calc_type === "sf" ? "SF" : f.calc_type === "lf" ? "LF" : "ea",
        unit_price: rate,
        total_price:
          f.total_price !== ""
            ? Number(f.total_price)
            : (quantity ?? 0) * (rate ?? 0),
      },
    ]);
  }
  const s = schema.data;
  return (
    <>
      <Modal title={t("Add line items")} onClose={onClose} wide>
        <div className="modal-tabs segments">
          {[
            ["calculator", t("Price calculator")],
            ["manual", t("Manual item")],
            ["services", t("Services")],
            ["catalog", t("Price book")],
          ].map(([value, label]) => (
            <button
              key={value}
              aria-pressed={tab === value}
              onClick={() => {
                setTab(value as typeof tab);
                setResult(null);
                setError("");
              }}
            >
              {t(label)}
            </button>
          ))}
        </div>
        <p className="modal-intro">
          {t(
            tab === "calculator"
              ? "Calculate a scope from dimensions and selected options, then add it to the zone."
              : tab === "manual"
                ? "Add a custom work item with your own quantity and price."
                : tab === "catalog"
                  ? "Select a saved Price Book item and set its quantity."
                  : "Choose a service, then set its project price in the estimate.",
          )}
        </p>
        {error ? (
          <div className="modal-error">
            <ErrorNotice>{error}</ErrorNotice>
          </div>
        ) : null}
        {tab === "manual" ? (
          <form onSubmit={manual}>
            <div className="modal-body form-grid">
              <Field label={t("Item name")} className="span-all">
                <input
                  name="name"
                  required
                  autoComplete="off"
                  maxLength={500}
                />
              </Field>
              <Field label={t("Section")}>
                <input
                  name="section"
                  defaultValue="General"
                  autoComplete="off"
                />
              </Field>
              <Field label={t("Calculation type")}>
                <Select name="calc_type">
                  <option value="manual">{t("Manual")}</option>
                  <option value="fixed">{t("Fixed / quantity")}</option>
                  <option value="sf">{t("Square feet")}</option>
                  <option value="lf">{t("Linear feet")}</option>
                </Select>
              </Field>
              <Field label={t("Quantity")}>
                <input type="number" name="quantity" min="0" step="0.01" />
              </Field>
              <Field label={t("Unit price ($)")}>
                <input type="number" name="unit_price" min="0" step="0.01" />
              </Field>
              <Field
                label={t("Total ($)")}
                hint={t("Leave blank to use quantity × unit price.")}
                className="span-all"
              >
                <input type="number" name="total_price" min="0" step="0.01" />
              </Field>
              <Field label={t("Description")} className="span-all">
                <textarea name="description" rows={3} />
              </Field>
            </div>
            <footer className="modal-footer">
              <Button onClick={onClose}>{t("Cancel")}</Button>
              <Button type="submit" variant="primary" busy={busy}>
                {t("Add item")}
              </Button>
            </footer>
          </form>
        ) : tab === "catalog" ? (
          <CatalogPicker
            key={selectedCatalog?.id || "catalog"}
            initialItem={selectedCatalog}
            onCreate={openCreate}
            onAdd={add}
            onClose={onClose}
          />
        ) : schema.isLoading ? (
          <Loading />
        ) : !s ? (
          <div className="modal-body">
            <ErrorNotice retry={() => schema.refetch()}>
              {errorMessage(schema.error)}
            </ErrorNotice>
          </div>
        ) : tab === "services" ? (
          <div className="modal-body service-list">
            {Object.entries(s.services).map(([key, service]) => (
              <div key={key}>
                <span>
                  {t(service.label)}
                  <small>
                    {service.default_price
                      ? money(service.default_price)
                      : t("Add now; set the project price in your estimate.")}
                  </small>
                </span>
                <Button
                  busy={busy}
                  onClick={() =>
                    add([
                      {
                        name: service.label,
                        section: "Services",
                        calc_type: "fixed",
                        quantity: 1,
                        unit: service.unit,
                        unit_price: service.default_price,
                        total_price: service.default_price,
                      },
                    ])
                  }
                >
                  {t("Add service")}
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <>
            <form onSubmit={calculate} onChange={() => setResult(null)}>
              <div className="modal-body">
                <div className="form-grid">
                  <Field label={t("Calculator or Price Book item")}>
                    <SearchSelect
                      value={`calculator:${type}`}
                      disabled={busy || !catalog.data}
                      options={[
                        ...(
                          [
                            ["wall", "Wall panels"],
                            ["cabinet", "Cabinetry"],
                            ["mirror", "Mirror"],
                          ] as const
                        ).map(([value, label]) => ({
                          value: `calculator:${value}`,
                          label: t(label),
                          keywords: `${label} ${value} ${t("Price calculator")}`,
                        })),
                        ...catalogItems.map((item) => ({
                          value: `item:${item.id}`,
                          label: `${localized(item, language, t)} · ${item.pricing_mode === "unpriced" ? t("Price pending") : money(item.unit_price)}`,
                          keywords: `${item.name} ${item.name_ru} ${item.description} ${item.description_ru}`,
                        })),
                      ]}
                      onCreate={openCreate}
                      onSelect={(value) => {
                        if (value.startsWith("item:")) {
                          const item = catalogItems.find(
                            (i) => `item:${i.id}` === value,
                          );
                          if (item) {
                            setSelectedCatalog(item);
                            setTab("catalog");
                          }
                          return;
                        }
                        setType(value.slice("calculator:".length));
                        setChecked([]);
                        setFixed({});
                        setResult(null);
                      }}
                    />
                  </Field>
                  {catalog.error ? (
                    <div className="span-all">
                      <ErrorNotice retry={() => catalog.refetch()}>
                        {errorMessage(catalog.error)}
                      </ErrorNotice>
                    </div>
                  ) : null}
                  {type === "cabinet" ? (
                    <Field label={t("Linear footage (LF)")}>
                      <input
                        key="lf"
                        type="number"
                        name="linear_footage"
                        required
                        min="0"
                        step="0.01"
                        defaultValue={zone.linear_footage ?? ""}
                      />
                    </Field>
                  ) : (
                    <Field label={t("Square footage (SF)")}>
                      <input
                        key="sf"
                        type="number"
                        name="square_footage"
                        required
                        min="0"
                        step="0.01"
                        defaultValue={zone.square_footage ?? ""}
                      />
                    </Field>
                  )}
                  {type === "wall" ? (
                    <>
                      <Field label="Panel / material name">
                        <Combobox
                          name="panel_name"
                          options={Object.values(s.materials).map(
                            (material) => ({
                              value: material.label,
                              label: t(material.label),
                            }),
                          )}
                          onValueChange={(value) => {
                            setResult(null);
                            const material = Object.values(s.materials).find(
                              (m) => m.label === value,
                            );
                            if (material)
                              setChecked((current) => [
                                ...current.filter(
                                  (k) =>
                                    ![
                                      "premium_material",
                                      "very_premium_material",
                                    ].includes(k),
                                ),
                                ...(material.addon_key
                                  ? [material.addon_key]
                                  : []),
                              ]);
                          }}
                        />
                      </Field>
                      <Field label="Color / finish">
                        <Combobox
                          name="panel_color"
                          onValueChange={() => setResult(null)}
                          options={s.colors
                            .flatMap((group) => group.options)
                            .map((value) => ({ value, label: t(value) }))}
                        />
                      </Field>
                      <Field
                        label={t("Panel coverage (%)")}
                        hint={t("Leave blank for the full wall.")}
                      >
                        <input
                          type="number"
                          name="panel_coverage_pct"
                          min="1"
                          max="100"
                        />
                      </Field>
                      <p className="form-hint">
                        {t(
                          "Base wall rate follows the existing small / medium / large SF pricing tiers. Select material upgrades below.",
                        )}
                      </p>
                    </>
                  ) : type === "cabinet" ? (
                    <>
                      <Field label={t("Cabinet type")}>
                        <Select name="cabinet_type">
                          <option value="">{t("Standard cabinetry")}</option>
                          {s.cabinet.types.map((v) => (
                            <option key={v.key} value={v.key}>
                              {t(v.label)} · {money(v.rate)}/LF
                            </option>
                          ))}
                        </Select>
                      </Field>
                      <label className="check-label">
                        <input type="checkbox" name="budget" />
                        <span>
                          {t("Budget base rate")}
                          <small>
                            {t("Applies only to Standard cabinetry.")}
                          </small>
                        </span>
                      </label>
                    </>
                  ) : (
                    <p className="form-hint">
                      {money(s.mirror.rate)}/SF + {money(s.mirror.minimum)}{" "}
                      {t("installation fee.")}
                    </p>
                  )}
                </div>
                {type !== "mirror" ? (
                  <fieldset className="addon-fieldset">
                    <legend>
                      {type === "wall"
                        ? t("Material & installation upgrades")
                        : t("Cabinetry upgrades")}
                    </legend>
                    <div className="check-grid">
                      {(type === "wall"
                        ? s.wall.addons_sf
                        : s.cabinet.addons_lf
                      ).map((v) => (
                        <label className="check-label" key={v.key}>
                          <input
                            type="checkbox"
                            checked={checked.includes(v.key)}
                            onChange={() => toggle(v.key)}
                          />
                          <span>
                            {t(v.label)}
                            <small>
                              +{money(v.price)}/{type === "wall" ? "SF" : "LF"}
                            </small>
                          </span>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ) : null}
                {type !== "mirror" ? (
                  <fieldset className="addon-fieldset">
                    <legend>
                      {type === "wall"
                        ? t("Doors & fixed additions")
                        : t("Glass doors")}
                    </legend>
                    <div className="form-grid">
                      {(type === "wall"
                        ? s.wall.addons_fixed
                        : s.cabinet.glass_doors
                      ).map((v) => (
                        <Field
                          label={t(
                            "{0} ({1} each)",
                            t(v.label),
                            money(v.price),
                          )}
                          key={v.key}
                        >
                          <input
                            type="number"
                            min="0"
                            step="1"
                            value={fixed[v.key] ?? 0}
                            onChange={(e) =>
                              setFixed((f) => ({
                                ...f,
                                [v.key]: Number(e.target.value),
                              }))
                            }
                          />
                        </Field>
                      ))}
                    </div>
                  </fieldset>
                ) : null}
              </div>
              <footer className="modal-footer">
                <Button onClick={onClose}>{t("Cancel")}</Button>
                <Button type="submit" busy={busy}>
                  {t("Calculate price")}
                </Button>
              </footer>
            </form>
            {result ? (
              <div className="calculation-result">
                <h3>{t("Calculated scope")}</h3>
                {result.line_items.map((item, i) => (
                  <div key={i}>
                    <span>{item.name}</span>
                    <strong>{money(item.total_price)}</strong>
                  </div>
                ))}
                <div className="result-total">
                  <span>{t("Total to add")}</span>
                  <strong>{money(result.total)}</strong>
                </div>
                <Button
                  variant="primary"
                  busy={busy}
                  onClick={() => add(result.line_items)}
                >
                  {t("Add items to zone ({0})", result.line_items.length)}
                </Button>
              </div>
            ) : null}
          </>
        )}
      </Modal>
      {createItem && catalog.data ? (
        <ItemForm
          categoryId={
            categories.some((c) => c.id === createItem.category)
              ? createItem.category
              : categories[0]?.id || "wall"
          }
          categories={categories}
          initialName={createItem.name}
          addToZone
          onClose={() => setCreateItem(null)}
          onSaved={savedItem}
        />
      ) : null}
    </>
  );
}
