import Select from "../components/Select";
import { useI18n } from "../lib/i18n";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ArrowRight, Save } from "lucide-react";
import { Button, Field, PageHeader, useNotice } from "../components/ui";
import {
  calculateRoom,
  roomTypes,
  roomOptions,
  type QuickRoom,
} from "../lib/quickEstimate";
import { post, patch, money, errorMessage } from "../lib/api";
import type { Estimate, Zone } from "../lib/types";
import { useAuth } from "../lib/auth";
import PreparedBy from "../components/PreparedBy";
export default function QuickEstimate() {
  const { t } = useI18n();

  const [rooms, setRooms] = useState<QuickRoom[]>([]);
  const [roomType, setRoomType] = useState("living_room");
  const [busy, setBusy] = useState(false);
  const [partialId, setPartialId] = useState<string | null>(null);
  const [markup, setMarkup] = useState(0);
  const [discount, setDiscount] = useState(0);
  const notify = useNotice();
  const navigate = useNavigate();
  const client = useQueryClient();
  const { user } = useAuth();
  const subtotal = rooms
    .flatMap(calculateRoom)
    .reduce((sum, i) => sum + Number(i.total_price), 0);
  const total = subtotal * (1 + markup / 100) * (1 - discount / 100);
  useEffect(() => {
    if (!rooms.length || partialId) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [rooms.length, partialId]);
  function addRoom() {
    setRooms((old) => [
      ...old,
      {
        id: crypto.randomUUID(),
        room_type: roomType,
        label: roomTypes.find(([key]) => key === roomType)![1],
        width_ft: 0,
        height_ft: 0,
        options: roomType === "kitchen" ? { tier: "budget" } : {},
      },
    ]);
  }
  function changeRoom(id: string, fields: Partial<QuickRoom>) {
    setRooms((old) => old.map((r) => (r.id === id ? { ...r, ...fields } : r)));
  }
  function option(
    room: QuickRoom,
    key: string,
    value: string | number | boolean,
  ) {
    changeRoom(room.id, { options: { ...room.options, [key]: value } });
  }
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!rooms.length)
      return notify("Add at least one room before saving.", true);
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    let created: string | undefined;
    try {
      const estimate = await post<Estimate>("/estimates", {
        ...fields,
        type: "quick",
      });
      created = estimate.id;
      for (let index = 0; index < rooms.length; index++) {
        const room = rooms[index];
        const zone = await post<Zone>(`/estimates/${estimate.id}/zones`, {
          zone_type: "wall",
          label: room.label,
          room_name: room.label,
          wall_width_ft: room.width_ft || null,
          wall_height_ft: room.height_ft || null,
          square_footage:
            room.width_ft && room.height_ft
              ? room.width_ft * room.height_ft
              : null,
          sort_order: index,
        });
        const items = calculateRoom(room);
        for (let i = 0; i < items.length; i++)
          await post(`/estimates/${estimate.id}/line-items`, {
            ...items[i],
            zone_id: zone.id,
            sort_order: i,
          });
      }
      if (markup || discount)
        await patch(`/estimates/${estimate.id}`, {
          markup_pct: markup || null,
          discount_pct: discount || null,
        });
      setPartialId(estimate.id);
      await client.invalidateQueries({ queryKey: ["estimates"] });
      notify("Quick estimate saved");
      navigate(`/estimates/${estimate.id}`);
    } catch (err) {
      if (created) setPartialId(created);
      notify(
        `${errorMessage(err)}${created ? " Your partial draft is available below." : ""}`,
        true,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeader
        title={t("Quick estimate")}
        description={t("Build a starting scope from familiar room templates.")}
        actions={
          <Link to="/" className="button ghost">
            {t("Back to estimates")}
          </Link>
        }
      />
      <form className="quick-layout" onSubmit={save}>
        <div className="quick-main">
          <section className="quick-project">
            <h2>{t("Project details")}</h2>
            <div className="form-grid">
              <Field label={t("Client name")}>
                <input name="client_name" required autoComplete="off" />
              </Field>
              <Field label={t("Project name")}>
                <input name="project_name" autoComplete="off" />
              </Field>
              <Field label={t("Estimate title")}>
                <input
                  name="title"
                  defaultValue="Quick Estimate"
                  required
                  autoComplete="off"
                />
              </Field>
              <PreparedBy name={user?.name || user?.email || ""} />
              <Field label={t("Date")}>
                <input
                  name="estimate_date"
                  type="date"
                  defaultValue={new Date().toLocaleDateString("en-CA")}
                  required
                />
              </Field>
            </div>
          </section>
          <section className="quick-rooms">
            <div className="section-heading">
              <div>
                <h2>{t("Rooms & spaces")}</h2>
                <p>{t("Add rooms, dimensions, and the relevant options.")}</p>
              </div>
            </div>
            <div className="quick-room-toolbar">
              <Field label={t("Room template")}>
                <Select
                  aria-label={t("Room template")}
                  value={roomType}
                  onChange={(e) => setRoomType(e.target.value)}
                >
                  {roomTypes.map(([key, label]) => (
                    <option key={key} value={key}>
                      {t(label)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Button onClick={addRoom}>
                <Plus size={16} />
                {t("Add room")}
              </Button>
            </div>
            {!rooms.length ? (
              <div className="quick-empty">
                {t("Choose a room template to begin your scope.")}
              </div>
            ) : (
              rooms.map((room, index) => {
                const items = calculateRoom(room);
                return (
                  <section className="quick-room" key={room.id}>
                    <header>
                      <span className="subtle-label">
                        {t("Room")} {index + 1}
                      </span>
                      <strong>
                        {t(
                          roomTypes.find(
                            ([key]) => key === room.room_type,
                          )?.[1] || "Room",
                        )}
                      </strong>
                      <Button
                        variant="ghost"
                        aria-label={t("Remove room {0}", room.label)}
                        onClick={() =>
                          setRooms((old) => old.filter((r) => r.id !== room.id))
                        }
                      >
                        <Trash2 size={16} />
                      </Button>
                    </header>
                    <div className="form-grid">
                      <Field label={t("Room name")} className="span-all">
                        <input
                          value={room.label}
                          required
                          onChange={(e) =>
                            changeRoom(room.id, { label: e.target.value })
                          }
                          autoComplete="off"
                        />
                      </Field>
                      <Field label={t("Width (ft)")}>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={room.width_ft || ""}
                          onChange={(e) =>
                            changeRoom(room.id, {
                              width_ft: Number(e.target.value),
                            })
                          }
                        />
                      </Field>
                      <Field label={t("Height (ft)")}>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={room.height_ft || ""}
                          onChange={(e) =>
                            changeRoom(room.id, {
                              height_ft: Number(e.target.value),
                            })
                          }
                        />
                      </Field>
                    </div>
                    {roomOptions[room.room_type]?.length ||
                    ["living_room", "home_office", "kitchen"].includes(
                      room.room_type,
                    ) ? (
                      <fieldset className="quick-room-options">
                        <legend>{t("Room options")}</legend>
                        <div className="form-grid">
                          {(roomOptions[room.room_type] || []).map(
                            ([key, label]) => (
                              <Field label={t(label)} key={key}>
                                <input
                                  type="number"
                                  min="0"
                                  step={key === "bottle_racks" ? "1" : ".01"}
                                  value={
                                    Number(
                                      room.options[key] ??
                                        (key === "nightstand_lf"
                                          ? 4
                                          : key === "bottle_racks"
                                            ? 1
                                            : 0),
                                    ) || ""
                                  }
                                  onChange={(e) =>
                                    option(room, key, Number(e.target.value))
                                  }
                                />
                              </Field>
                            ),
                          )}
                          {room.room_type === "home_office" ? (
                            <Field label={t("Desk tier")}>
                              <Select
                                value={String(
                                  room.options.desk_tier || "budget",
                                )}
                                onChange={(e) =>
                                  option(room, "desk_tier", e.target.value)
                                }
                              >
                                <option value="budget">{t("Budget")}</option>
                                <option value="highend">{t("High-end")}</option>
                              </Select>
                            </Field>
                          ) : null}
                          {room.room_type === "kitchen" ? (
                            <Field label={t("Kitchen tier")}>
                              <Select
                                value={String(room.options.tier || "budget")}
                                onChange={(e) =>
                                  option(room, "tier", e.target.value)
                                }
                              >
                                <option value="budget">{t("Budget")}</option>
                                <option value="highend">{t("High-end")}</option>
                              </Select>
                            </Field>
                          ) : null}
                        </div>
                        {["living_room", "home_office"].includes(
                          room.room_type,
                        ) ? (
                          <div className="quick-room-toggles">
                            <label className="quick-option-toggle">
                              <input
                                type="checkbox"
                                aria-labelledby={`${room.id}-option-label`}
                                aria-describedby={`${room.id}-option-hint`}
                                checked={
                                  !!room.options[
                                    room.room_type === "living_room"
                                      ? "fireplace"
                                      : "wall_panels"
                                  ]
                                }
                                onChange={(event) =>
                                  option(
                                    room,
                                    room.room_type === "living_room"
                                      ? "fireplace"
                                      : "wall_panels",
                                    event.target.checked,
                                  )
                                }
                              />
                              <span>
                                <strong id={`${room.id}-option-label`}>
                                  {t(
                                    room.room_type === "living_room"
                                      ? "Include fireplace"
                                      : "Include wall panels",
                                  )}
                                </strong>
                                <small id={`${room.id}-option-hint`}>
                                  {t(
                                    room.room_type === "living_room"
                                      ? "Adds the fireplace unit and installation to this room."
                                      : "Uses this room’s width and height to calculate panel area.",
                                  )}
                                </small>
                              </span>
                            </label>
                          </div>
                        ) : null}
                      </fieldset>
                    ) : null}
                    <details className="quick-scope">
                      <summary>
                        {t("Items in this room: {0}", items.length)}{" "}
                        <strong>
                          {money(
                            items.reduce(
                              (sum, i) => sum + Number(i.total_price),
                              0,
                            ),
                          )}
                        </strong>
                      </summary>
                      {items.map((i, n) => (
                        <div key={n}>
                          <span>{i.name}</span>
                          <span>
                            {Number(i.total_price)
                              ? money(i.total_price)
                              : t("Set in estimate")}
                          </span>
                        </div>
                      ))}
                    </details>
                  </section>
                );
              })
            )}
          </section>
        </div>
        <aside className="quick-summary">
          <h2>{t("Project summary")}</h2>
          {rooms.map((r) => (
            <div className="quick-summary-row" key={r.id}>
              <span>{r.label}</span>
              <strong>
                {money(
                  calculateRoom(r).reduce(
                    (s, i) => s + Number(i.total_price),
                    0,
                  ),
                )}
              </strong>
            </div>
          ))}
          <Field label={t("Markup (%)")}>
            <input
              type="number"
              min="0"
              max="200"
              step="0.5"
              value={markup}
              onChange={(e) => setMarkup(Number(e.target.value))}
            />
          </Field>
          <Field label={t("Discount (%)")}>
            <input
              type="number"
              min="0"
              max="100"
              step="0.5"
              value={discount}
              onChange={(e) => setDiscount(Number(e.target.value))}
            />
          </Field>
          <div className="grand-total">
            <span>{t("Grand total")}</span>
            <strong>{money(total)}</strong>
          </div>
          <p className="summary-note">
            {t(
              "Review line items, service prices, and photos in the builder before sharing.",
            )}
          </p>
          {partialId ? (
            <Link
              className="button primary full-width"
              to={`/estimates/${partialId}`}
            >
              {t("Open saved draft")}
              <ArrowRight size={16} />
            </Link>
          ) : (
            <Button
              className="full-width"
              type="submit"
              variant="primary"
              busy={busy}
              disabled={!rooms.length}
            >
              <Save size={16} />
              {t("Save & open estimate")}
            </Button>
          )}
        </aside>
      </form>
    </>
  );
}
