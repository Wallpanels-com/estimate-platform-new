import Select from "./Select";
import AutosaveNumber from "./AutosaveNumber";
import { useI18n } from "../lib/i18n";
import { useId, useState } from "react";
import { ArrowDown, ArrowUp, Pencil, Trash2 } from "lucide-react";
import { Button, Field, Modal } from "./ui";
import ActionMenu from "./ActionMenu";
import { money } from "../lib/api";
import type { LineItem } from "../lib/types";
interface Props {
  items: LineItem[];
  busy: boolean;
  onUpdate: (id: string, fields: Record<string, unknown>) => Promise<boolean>;
  onDelete: (item: LineItem) => void;
  onMove: (id: string, direction: number) => void;
  onPendingChange?: (key: string, pending: boolean) => void;
}

export function Description({ text }: { text: string }) {
  const { t } = useI18n();

  const [expanded, setExpanded] = useState(false);
  const id = useId();
  return (
    <div className="item-description">
      <p
        id={id}
        className={
          !expanded && (text.length > 100 || text.includes("\n"))
            ? "description-preview"
            : ""
        }
      >
        {text}
      </p>
      {text.length > 100 || text.includes("\n") ? (
        <button
          type="button"
          className="text-action"
          aria-expanded={expanded}
          aria-controls={id}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? t("Show less") : t("Read description")}
        </button>
      ) : null}
    </div>
  );
}

function ItemEditor({
  item,
  busy,
  onSave,
  onClose,
}: {
  item: LineItem;
  busy: boolean;
  onSave: Props["onUpdate"];
  onClose: () => void;
}) {
  const { t } = useI18n();

  const [unit, setUnit] = useState(item.unit || "");
  return (
    <Modal title={t("Edit line item")} onClose={onClose}>
      <form
        autoComplete="off"
        onSubmit={async (event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          const changes: Record<string, unknown> = {};
          for (const field of [
            "name",
            "description",
            "section",
            "unit",
            "calc_type",
          ] as const) {
            const value = String(data.get(field) || "").trim();
            if (value !== (item[field] || "")) changes[field] = value || null;
          }
          // Quantity / rate changes use the existing API calculation.
          for (const field of [
            "quantity",
            "unit_price",
            "total_price",
          ] as const) {
            const raw = data.get(field);
            const value =
              raw === "" ? (field === "total_price" ? 0 : null) : Number(raw);
            if (value !== (item[field] == null ? null : Number(item[field])))
              changes[field] = value;
          }
          const tbd = data.has("is_tbd");
          if (tbd !== item.is_tbd) changes.is_tbd = tbd;
          if (!Object.keys(changes).length) return onClose();
          // Metadata edits must preserve an existing fixed fee or manual total.
          if (!(
            "quantity" in changes ||
            "unit_price" in changes ||
            "total_price" in changes
          ))
            changes.total_price = Number(item.total_price);
          if (await onSave(item.id, changes)) onClose();
        }}
      >
        <div className="modal-body form-grid">
          <Field label={t("Item name")} className="span-all">
            <input
              name="name"
              defaultValue={item.name}
              required
              disabled={busy}
            />
          </Field>
          <Field label={t("Description")} className="span-all">
            <textarea
              name="description"
              defaultValue={item.description || ""}
              rows={5}
              disabled={busy}
            />
          </Field>
          <Field label={t("Section")}>
            <input
              name="section"
              defaultValue={item.section || ""}
              disabled={busy}
            />
          </Field>
          <Field label={t("Calculation type")}>
            <Select
              name="calc_type"
              defaultValue={item.calc_type}
              onChange={(e) =>
                setUnit(
                  e.target.value === "sf"
                    ? "SF"
                    : e.target.value === "lf"
                      ? "LF"
                      : "ea",
                )
              }
              disabled={busy}
            >
              <option value="sf">{t("Square feet (SF)")}</option>
              <option value="lf">{t("Linear feet (LF)")}</option>
              <option value="fixed">{t("Fixed")}</option>
              <option value="manual">{t("Manual")}</option>
            </Select>
          </Field>
          <Field label={t("Quantity")}>
            <input
              name="quantity"
              type="number"
              min="0"
              step="0.01"
              defaultValue={item.quantity ?? ""}
              disabled={busy}
            />
          </Field>
          <Field label={t("Unit")}>
            <input
              name="unit"
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              disabled={busy}
            />
          </Field>
          <Field label={t("Unit price")}>
            <input
              name="unit_price"
              type="number"
              placeholder={t("Not set")}
              title={t("Price for 1 {0}", unit || "unit")}
              min="0"
              step="0.01"
              defaultValue={item.unit_price ?? ""}
              disabled={busy}
            />
          </Field>
          <Field label={t("Total")}>
            <input
              name="total_price"
              type="number"
              min="0"
              step="0.01"
              defaultValue={item.total_price ?? 0}
              disabled={busy}
            />
          </Field>
          <label className="check-label span-all">
            <input
              type="checkbox"
              name="is_tbd"
              defaultChecked={item.is_tbd}
              disabled={busy}
            />
            {t("Price to be confirmed")}
          </label>
          {item.original_unit_price != null &&
          Number(item.original_unit_price) !== Number(item.unit_price) ? (
            <p className="form-hint span-all">
              {t("Original unit price:")}
              {money(item.original_unit_price)}
            </p>
          ) : null}
        </div>
        <footer className="modal-footer">
          <Button onClick={onClose} disabled={busy}>
            {t("Cancel")}
          </Button>
          <Button type="submit" variant="primary" busy={busy}>
            {t("Save changes")}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}

const displayUnit = (item: LineItem) =>
  item.unit ||
  (item.calc_type === "sf"
    ? "SF"
    : item.calc_type === "lf"
      ? "LF"
      : item.calc_type === "fixed"
        ? "ea"
        : "");

export default function LineItems({
  items,
  busy,
  onUpdate,
  onDelete,
  onMove,
  onPendingChange,
}: Props) {
  const { t, n } = useI18n();

  const [editing, setEditing] = useState<LineItem | null>(null);
  const groups = new Map<string, LineItem[]>();
  for (const item of items) {
    const section = item.section || "General";
    const group = groups.get(section);
    if (group) group.push(item);
    else groups.set(section, [item]);
  }
  return (
    <div
      className={`line-sections ${items.length > 50 ? "large-estimate" : ""}`}
    >
      {[...groups].map(([section, group]) => {
        return (
          <section className="line-section" key={section}>
            <header>
              <div>
                <h3>{t(section)}</h3>
                <span>{n(group.length, "items")}</span>
              </div>
              <strong>
                {group.every((i) => i.is_tbd) &&
                group.every((i) => Number(i.total_price) === 0)
                  ? t("Pricing pending")
                  : money(
                      group.reduce((sum, i) => sum + Number(i.total_price), 0),
                    )}
              </strong>
            </header>
            <div className="line-head" aria-hidden="true">
              <span>{t("Work item")}</span>
              <span>{t("Quantity")}</span>
              <span>{t("Unit price")}</span>
              <span>{t("Total")}</span>
              <span />
            </div>
            {group.map((item) => (
              <div
                className="line-item"
                key={item.id}
                data-testid="line-item"
                role="group"
                aria-label={item.name}
              >
                <div className="line-description">
                  <button
                    type="button"
                    className="item-name"
                    title={item.name}
                    onClick={() => setEditing(item)}
                    disabled={busy}
                  >
                    {item.name}
                  </button>
                  {item.description ? (
                    <Description text={item.description} />
                  ) : null}
                </div>
                {["manual", "fixed"].includes(item.calc_type) &&
                item.quantity == null &&
                item.unit_price == null &&
                Number(item.total_price) > 0 ? (
                  <div className="fixed-amount-label">{t("Fixed amount")}</div>
                ) : (
                  (["quantity", "unit_price"] as const).map((field) => (
                    <label
                      className={`line-cell ${field === "quantity" ? "quantity-cell" : ""}`}
                      key={field}
                    >
                      <span>
                        {field === "quantity" ? t("Quantity") : t("Unit price")}
                      </span>
                      <div className="number-control">
                        <AutosaveNumber
                          aria-label={t(
                            "{0} for {1}",
                            field === "quantity"
                              ? t("Quantity")
                              : t("Unit price"),
                            item.name,
                          )}
                          type="number"
                          step="0.01"
                          min="0"
                          name={`${field}-${item.id}`}
                          key={`${item.id}-${field}`}
                          onPendingChange={(pending) =>
                            onPendingChange?.(`${item.id}-${field}`, pending)
                          }
                          initialValue={item[field] ?? null}
                          placeholder={
                            field === "unit_price" ? t("Not set") : undefined
                          }
                          title={
                            field === "unit_price"
                              ? t(
                                  "Price for 1 {0}{1}",
                                  displayUnit(item) || "unit",
                                  item.unit_price == null
                                    ? t("; not set yet")
                                    : "",
                                )
                              : undefined
                          }
                          disabled={busy}
                          onSave={(next) =>
                            onUpdate(item.id, { [field]: next })
                          }
                        />
                        {field === "quantity" && displayUnit(item) ? (
                          <small>{displayUnit(item)}</small>
                        ) : null}
                      </div>
                    </label>
                  ))
                )}
                <div className="line-cell line-total">
                  <span>{t("Total")}</span>
                  <button
                    className={`item-total${item.is_tbd ? " is-pending" : ""}`}
                    type="button"
                    disabled={busy}
                    aria-label={t("Edit total for {0}", item.name)}
                    title={
                      item.is_tbd
                        ? t(
                            "Price has not been confirmed. Open this item to set the price.",
                          )
                        : undefined
                    }
                    onClick={() => setEditing(item)}
                  >
                    {item.is_tbd ? t("Price pending") : money(item.total_price)}
                  </button>
                </div>
                <div className="line-actions">
                  <ActionMenu
                    label={t("Actions for {0}", item.name)}
                    disabled={busy}
                    actions={[
                      {
                        label: "Edit item",
                        icon: <Pencil size={15} />,
                        onSelect: () => setEditing(item),
                      },
                      {
                        label: "Move up",
                        icon: <ArrowUp size={15} />,
                        disabled: items[0].id === item.id,
                        onSelect: () => onMove(item.id, -1),
                      },
                      {
                        label: "Move down",
                        icon: <ArrowDown size={15} />,
                        disabled: items[items.length - 1].id === item.id,
                        onSelect: () => onMove(item.id, 1),
                      },
                      {
                        label: "Delete item",
                        icon: <Trash2 size={15} />,
                        danger: true,
                        onSelect: () => onDelete(item),
                      },
                    ]}
                  />
                </div>
              </div>
            ))}
          </section>
        );
      })}
      {editing ? (
        <ItemEditor
          item={editing}
          busy={busy}
          onSave={onUpdate}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </div>
  );
}
