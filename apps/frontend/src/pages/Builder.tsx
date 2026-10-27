import { LanguageSwitch, useI18n } from "../lib/i18n";
import { useState, useEffect, useCallback, useRef } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Plus,
  Settings2,
  Download,
  FileSpreadsheet,
  Copy,
  Trash2,
  ChevronUp,
  ChevronDown,
  Check,
  Sparkles,
  Pencil,
  Image,
  List,
  Layers,
  Eye,
  History,
} from "lucide-react";
import {
  request,
  post,
  patch,
  remove,
  money,
  errorMessage,
  download,
  safeFilename,
} from "../lib/api";
import type { Estimate, Zone, LineItem, CalculatedItem } from "../lib/types";
import { Brand } from "../components/Shell";
import {
  Button,
  Confirm,
  EmptyState,
  ErrorNotice,
  Loading,
  useNotice,
} from "../components/ui";
import EstimateForm from "../components/EstimateForm";
import ZoneForm from "../components/ZoneForm";
import LineItems, { Description } from "../components/LineItems";
import ActionMenu from "../components/ActionMenu";
import AddItems from "../components/AddItems";
import Photos from "../components/Photos";
import EstimateRecords from "../components/EstimateRecords";
import AiInput from "../components/AiInput";
import EstimatePdfPreview from "../components/EstimatePdfPreview";
import PdfChecks, { type ExportChecks } from "../components/PdfChecks";
import {
  createEstimatePdfLoader,
  downloadEstimatePdf,
  estimatePdfFilename,
  type EstimatePdfMode,
} from "../lib/estimatePdf";
const pricingPending = (zone: Zone) =>
  zone.line_items.some((i) => i.is_tbd) && Number(zone.subtotal) === 0;
export default function Builder() {
  const { t, n } = useI18n();

  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [params, setParams] = useSearchParams();
  const client = useQueryClient();
  const notify = useNotice();
  const [panel, setPanel] = useState("estimate");
  const [expandedZone, setExpandedZone] = useState<string | null>(null);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [panel]);
  const [proposal, setProposal] = useState(false);
  const [details, setDetails] = useState(false);
  const [records, setRecords] = useState(false);
  const [zoneForm, setZoneForm] = useState<"new" | "edit" | null>(null);
  const [adding, setAdding] = useState<
    "calculator" | "manual" | "services" | null
  >(null);
  const [ai, setAi] = useState(false);
  const capabilities = useQuery({
    queryKey: ["auth-settings"],
    queryFn: () => request<{ ai_enabled: boolean }>("/auth/settings"),
  });
  const [busy, setBusy] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);
  const [exporting, setExporting] = useState<"pdf" | "xlsx" | null>(null);
  const [deletingZone, setDeletingZone] = useState<Zone | null>(null);
  const [deletingItem, setDeletingItem] = useState<LineItem | null>(null);
  const query = useQuery({
    queryKey: ["estimate", id],
    queryFn: ({ signal }) => request<Estimate>(`/estimates/${id}`, { signal }),
    refetchInterval: () =>
      busy ||
      saveFailed ||
      document.querySelector(
        "dialog[open], input:focus, textarea:focus, select:focus",
      )
        ? false
        : 8000,
  });
  const estimate = query.data;
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (busy || saveFailed) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [busy, saveFailed]);
  const pdfMode: EstimatePdfMode = estimate?.type === "final" ? "final" : "pre";
  const pdfId = estimate?.id;
  const pdfRevision = estimate?.updated_at
    ? `${estimate.updated_at}${pdfMode === "final" ? ":final-sparse-summary-v9" : ":pre-clean-title-v4"}`
    : undefined;
  const pdfFilename = estimatePdfFilename(
    pdfMode,
    estimate?.client_name || "Client",
  );
  const pdfLoader = useRef<ReturnType<typeof createEstimatePdfLoader> | null>(
    null,
  );
  if (!pdfLoader.current) pdfLoader.current = createEstimatePdfLoader();
  const finalChecks = useQuery({
    queryKey: ["final-check", pdfId, pdfRevision],
    queryFn: ({ signal }) =>
      request<ExportChecks>(`/pdf/${pdfId}/final-check`, { signal }),
    enabled: !!pdfId && pdfMode === "final",
  });
  const loadPdf = useCallback(async () => {
    if (saveFailed || busy)
      throw new Error(t("Save your changes before exporting."));
    if (!pdfId || !pdfRevision)
      return Promise.reject(new Error("Estimate is not loaded."));
    if (pdfMode === "final") {
      const checks = await request<ExportChecks>(`/pdf/${pdfId}/final-check`);
      client.setQueryData(["final-check", pdfId, pdfRevision], checks);
      if (checks.errors.length)
        throw new Error(checks.errors.map((issue) => t(issue)).join(" "));
    }
    return pdfLoader.current!({
      id: pdfId,
      mode: pdfMode,
      revision: pdfRevision,
    });
  }, [pdfId, pdfMode, pdfRevision, client, t, saveFailed, busy]);
  const zones = estimate?.zones || [];
  const zone = zones.find((z) => z.id === params.get("zone")) || zones[0];
  async function refresh() {
    await client.invalidateQueries({ queryKey: ["estimate", id] });
    await client.invalidateQueries({ queryKey: ["estimates"] });
  }
  function selectZone(id: string) {
    setParams(
      (p) => {
        p.set("zone", id);
        return p;
      },
      { replace: true },
    );
  }
  async function mutate(
    task: () => Promise<unknown>,
    message = "Changes saved",
  ) {
    setBusy(true);
    try {
      await task();
      await refresh();
      setSaveFailed(false);
      notify(message);
      return true;
    } catch (err) {
      setSaveFailed(true);
      notify(errorMessage(err), true);
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function switchMode(mode: "pre" | "final") {
    if (estimate?.type === mode) return;
    setBusy(true);
    try {
      const next = await post<Estimate>(`/estimates/${id}/mode`, { mode });
      client.setQueryData(["estimate", next.id], next);
      await client.invalidateQueries({ queryKey: ["estimates"] });
      navigate(`/estimates/${next.id}`, { replace: true });
    } catch (err) {
      notify(errorMessage(err), true);
    } finally {
      setBusy(false);
    }
  }
  async function addItems(items: CalculatedItem[]) {
    if (!zone) return;
    for (let i = 0; i < items.length; i++)
      await post(`/estimates/${id}/line-items`, {
        ...items[i],
        zone_id: zone.id,
        sort_order: zone.line_items.length + i,
      });
    await refresh();
    notify("Line items added");
  }
  async function exportFile(kind: "pdf" | "xlsx") {
    if (!estimate) return;
    if (busy || saveFailed)
      return notify("Save your changes before exporting.", true);
    setExporting(kind);
    try {
      if (kind === "pdf") {
        downloadEstimatePdf(await loadPdf(), pdfFilename);
      } else
        await download(
          `/pdf/${id}/passport`,
          `Project passport - Wallpanels - ${safeFilename(estimate.client_name || "Client")}.xlsx`,
        );
      notify(kind === "pdf" ? "PDF downloaded" : "Project passport downloaded");
    } catch (err) {
      notify(errorMessage(err), true);
    } finally {
      setExporting(null);
    }
  }
  function moveZone(target: string, direction: number) {
    const order = zones.map((z) => z.id);
    const i = order.indexOf(target);
    const j = i + direction;
    if (j < 0 || j >= order.length) return;
    [order[i], order[j]] = [order[j], order[i]];
    mutate(() => post(`/estimates/${id}/zones/reorder`, order));
  }
  function moveItem(target: string, direction: number) {
    if (!zone) return;
    const order = [...zone.line_items]
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((i) => i.id);
    const i = order.indexOf(target);
    const j = i + direction;
    if (j < 0 || j >= order.length) return;
    [order[i], order[j]] = [order[j], order[i]];
    mutate(() =>
      post(`/estimates/${id}/line-items/reorder`, { ordered_ids: order }),
    );
  }
  if (query.isLoading) return <Loading label={t("Opening estimate…")} />;
  if (!estimate)
    return (
      <div className="error-page">
        <Link to="/" className="button secondary">
          <ArrowLeft size={16} />
          {t("Estimates")}
        </Link>
        <ErrorNotice retry={() => query.refetch()}>
          {errorMessage(query.error)}
        </ErrorNotice>
      </div>
    );
  const subtotal = zones.reduce((sum, z) => sum + Number(z.subtotal), 0);
  const marked = subtotal * (1 + Number(estimate.markup_pct || 0) / 100);
  const discount = (marked * Number(estimate.discount_pct || 0)) / 100;
  const total = marked - discount;
  const pendingZoneCount = zones.filter((z) =>
    z.line_items.some((i) => i.is_tbd),
  ).length;
  return (
    <div className="builder-root">
      <a href="#estimate-content" className="skip-link">
        {t("Skip to estimate")}
      </a>
      <header className="builder-header">
        <Link to="/" className="brand-link" aria-label={t("WallPanels home")}>
          <Brand />
        </Link>
        <div className="builder-heading">
          <Link to="/" className="back-link">
            <ArrowLeft size={17} />
            <span>{t("Estimates")}</span>
          </Link>
          <div className="min-zero">
            <h1 title={estimate.title || ""}>
              {estimate.title || t("Untitled estimate")}
            </h1>
            <span>
              {estimate.client_name || t("No client")}
              {estimate.project_name ? ` · ${estimate.project_name}` : ""}
            </span>
            <details className="estimate-authorship">
              <summary>
                {t("Prepared by")}:{" "}
                {estimate.prepared_by || estimate.created_by_name || "—"}
              </summary>
              <span>
                {t("Created by")}: {estimate.created_by_name || "—"} ·{" "}
                {t("Created at")}:{" "}
                {new Date(estimate.created_at).toLocaleString()} ·{" "}
                {t("Last edited by")}: {estimate.updated_by_name || "—"}
              </span>
            </details>
          </div>
        </div>
        <div className="builder-top-actions">
          <Button
            variant="ghost"
            aria-label={t("History & saved documents")}
            title={t("History & saved documents")}
            onClick={() => setRecords(true)}
            disabled={busy}
          >
            <History size={18} />
          </Button>
          <LanguageSwitch />
          <span className="save-state" role="status">
            <Check size={14} />
            {busy ? t("Saving…") : saveFailed ? t("Not saved") : t("Saved")}
          </span>
          <div className="segments type-switch" aria-label={t("Estimate type")}>
            <button
              aria-pressed={pdfMode === "pre"}
              disabled={busy || exporting === "pdf"}
              onClick={() => switchMode("pre")}
            >
              {t("Pre-estimate")}
            </button>
            <button
              aria-pressed={pdfMode === "final"}
              disabled={busy || exporting === "pdf"}
              onClick={() => switchMode("final")}
            >
              {t("Final")}
            </button>
          </div>
          <Button
            variant="ghost"
            aria-label={t("Edit estimate details, markup and discount")}
            title={t("Estimate details")}
            onClick={() => setDetails(true)}
          >
            <Settings2 size={18} />
          </Button>
        </div>
      </header>
      {records ? (
        <EstimateRecords id={estimate.id} onClose={() => setRecords(false)} />
      ) : null}
      <nav className="workspace-tabs" aria-label={t("Builder panels")}>
        {[
          ["estimate", t("Estimate"), List],
          ["photos", t("Photos"), Image],
          ["zones", t("Zones & summary"), Layers],
        ].map(([value, label, Icon]) => {
          const I = Icon as typeof List;
          return (
            <button
              key={String(value)}
              aria-pressed={panel === value}
              onClick={() => setPanel(String(value))}
            >
              <I size={17} />
              {t(String(label))}
            </button>
          );
        })}
      </nav>
      <div className="builder-workspace">
        <aside
          className={`photo-rail ${panel !== "photos" ? "mobile-panel-hidden" : ""}`}
        >
          {zone ? (
            <Photos
              key={zone.id}
              zone={zone}
              busy={busy}
              finalMode={pdfMode === "final"}
              presentationSlot={
                estimate?.pdf_layout?.final_zone_photos?.[zone.id]
              }
              onSelectPresentationPhoto={(slot) =>
                mutate(
                  () =>
                    request(
                      `/estimates/${id}/zones/${zone.id}/presentation-photo`,
                      {
                        method: "PUT",
                        body: JSON.stringify({ slot }),
                      },
                    ),
                  "Zone presentation photo saved",
                )
              }
              onUpload={(slot, file) =>
                mutate(async () => {
                  const body = new FormData();
                  body.append("file", file);
                  await request(
                    `/estimates/${id}/zones/${zone.id}/images/${slot}`,
                    { method: "POST", body },
                  );
                }, "Photo uploaded")
              }
              onDelete={(slot) =>
                mutate(
                  () =>
                    remove(`/estimates/${id}/zones/${zone.id}/images/${slot}`),
                  "Photo removed",
                )
              }
            />
          ) : (
            <div className="rail-empty">
              {t("Add a zone to attach photos.")}
            </div>
          )}
        </aside>
        <main
          id="estimate-content"
          className={`builder-main ${panel !== "estimate" ? "mobile-panel-hidden" : ""}`}
        >
          {zone ? (
            <>
              <header className="zone-overview">
                <div className="zone-overview-title">
                  <div>
                    <span className="subtle-label">
                      {zone.zone_type === "cabinet"
                        ? t("Cabinetry")
                        : zone.zone_type === "mirror"
                          ? t("Mirror")
                          : t("Wall panels")}
                    </span>
                    <h2
                      id={`zone-title-${zone.id}`}
                      className={
                        expandedZone === zone.id
                          ? undefined
                          : "zone-title-collapsed"
                      }
                    >
                      {zone.label}
                    </h2>
                    {zone.label.length > 80 ? (
                      <button
                        type="button"
                        className="text-action"
                        aria-expanded={expandedZone === zone.id}
                        aria-controls={`zone-title-${zone.id}`}
                        onClick={() =>
                          setExpandedZone(
                            expandedZone === zone.id ? null : zone.id,
                          )
                        }
                      >
                        {expandedZone === zone.id
                          ? t("Show less")
                          : t("Read zone name")}
                      </button>
                    ) : null}
                    {zone.room_name || zone.wall_name ? (
                      <p>
                        {[zone.room_name, zone.wall_name]
                          .filter(Boolean)
                          .join(" / ")}
                      </p>
                    ) : null}
                  </div>
                  <Button
                    variant="ghost"
                    aria-label={t("Edit zone")}
                    onClick={() => setZoneForm("edit")}
                  >
                    <Pencil size={15} />
                    <span>{t("Edit zone")}</span>
                  </Button>
                </div>
                {[
                  zone.wall_width_ft,
                  zone.wall_height_ft,
                  zone.square_footage,
                  zone.linear_footage,
                ].some((v) => v != null) ? (
                  <dl className="zone-dimensions">
                    {[
                      [t("Width"), zone.wall_width_ft, "ft"],
                      [t("Height"), zone.wall_height_ft, "ft"],
                      [t("Area"), zone.square_footage, "SF"],
                      [t("Length"), zone.linear_footage, "LF"],
                    ].map(([label, value, unit]) => (
                      <div key={String(label)}>
                        <dt>{t(String(label))}</dt>
                        <dd>
                          {value != null ? (
                            <>
                              {Number(value).toLocaleString("en-US")}{" "}
                              <span>{unit}</span>
                            </>
                          ) : (
                            "—"
                          )}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
                {zone.notes ? (
                  <div className="zone-notes">
                    <Description text={zone.notes} />
                  </div>
                ) : null}
              </header>
              <div className="scope-toolbar">
                <div>
                  <h2>{t("Scope of work")}</h2>
                  <span>{n(zone.line_items.length, "line items")}</span>
                </div>
                <div className="button-row">
                  <ActionMenu
                    label={t("More scope actions")}
                    disabled={busy}
                    actions={[
                      {
                        label: "Add manual item",
                        icon: <Plus size={16} />,
                        onSelect: () => setAdding("manual"),
                      },
                      {
                        label: "Add service",
                        icon: <Plus size={16} />,
                        onSelect: () => setAdding("services"),
                      },
                      ...(capabilities.data?.ai_enabled
                        ? [
                            {
                              label: "AI description",
                              icon: <Sparkles size={16} />,
                              onSelect: () => setAi(true),
                            },
                          ]
                        : []),
                    ]}
                  />
                  <Button
                    variant="primary"
                    onClick={() => setAdding("calculator")}
                  >
                    <Plus size={16} />
                    {t("Add items")}
                  </Button>
                </div>
              </div>
              {zone.line_items.length ? (
                <LineItems
                  key={zone.id}
                  items={[...zone.line_items].sort(
                    (a, b) => a.sort_order - b.sort_order,
                  )}
                  busy={busy}
                  onUpdate={(itemId, data) =>
                    mutate(() =>
                      patch(`/estimates/${id}/line-items/${itemId}`, data),
                    )
                  }
                  onDelete={setDeletingItem}
                  onMove={moveItem}
                />
              ) : (
                <EmptyState title={t("Build the scope for this zone")}>
                  {t(
                    "Calculate panels, cabinetry, or mirrors with your price book, or add a manual item.",
                  )}
                </EmptyState>
              )}
              <div className="scope-footer">
                <div>
                  <span>{t("Zone subtotal")}</span>
                  <strong>
                    {pricingPending(zone)
                      ? t("Pricing pending")
                      : money(zone.subtotal)}
                  </strong>
                </div>
              </div>
            </>
          ) : (
            <EmptyState
              title={t("Define your first zone")}
              action={
                <Button variant="primary" onClick={() => setZoneForm("new")}>
                  <Plus size={16} />
                  {t("Add zone")}
                </Button>
              }
            >
              {t("Organize the estimate by wall, room, or installation area.")}
            </EmptyState>
          )}
        </main>
        <aside
          className={`zones-rail ${panel !== "zones" ? "mobile-panel-hidden" : ""}`}
        >
          <section className="zones-list">
            <div className="rail-heading">
              <h2>{t("Project zones")}</h2>
              <span>{zones.length}</span>
            </div>
            <div className="zone-list-items">
              {zones.map((z, index) => (
                <div
                  className={`zone-card ${z.id === zone?.id ? "selected" : ""}`}
                  key={z.id}
                >
                  <button
                    className="zone-select"
                    title={z.label}
                    aria-current={z.id === zone?.id ? "true" : undefined}
                    onClick={() => {
                      selectZone(z.id);
                      setPanel("estimate");
                    }}
                  >
                    <span className="zone-card-index">
                      {t("Zone")} {index + 1}
                    </span>
                    <strong>{z.label}</strong>
                    <span className="zone-card-bottom">
                      <span>
                        {z.square_footage != null
                          ? `${Number(z.square_footage)} SF`
                          : z.linear_footage != null
                            ? `${Number(z.linear_footage)} LF`
                            : t("{0} items", z.line_items.length)}
                      </span>
                      <b>
                        {pricingPending(z)
                          ? t("Pricing pending")
                          : money(z.subtotal)}
                      </b>
                    </span>
                  </button>
                  <div className="zone-card-actions">
                    <ActionMenu
                      label={t("Actions for zone {0}", z.label)}
                      disabled={busy}
                      actions={[
                        {
                          label: "Move up",
                          icon: <ChevronUp size={15} />,
                          disabled: index === 0,
                          onSelect: () => moveZone(z.id, -1),
                        },
                        {
                          label: "Move down",
                          icon: <ChevronDown size={15} />,
                          disabled: index === zones.length - 1,
                          onSelect: () => moveZone(z.id, 1),
                        },
                        {
                          label: "Duplicate zone",
                          icon: <Copy size={15} />,
                          onSelect: () => {
                            void mutate(async () => {
                              const copy = await post<Zone>(
                                `/estimates/${id}/zones/${z.id}/duplicate`,
                              );
                              selectZone(copy.id);
                            }, "Zone duplicated");
                          },
                        },
                        {
                          label: "Delete zone",
                          icon: <Trash2 size={15} />,
                          danger: true,
                          onSelect: () => setDeletingZone(z),
                        },
                      ]}
                    />
                  </div>
                </div>
              ))}
            </div>
            <Button
              className="full-width"
              onClick={() => setZoneForm("new")}
              disabled={busy}
            >
              <Plus size={16} />
              {t("Add zone")}
            </Button>
          </section>
          <section
            className="project-summary"
            aria-label={t("Project summary")}
          >
            <div className="summary-heading">
              <h2>{t("Summary")}</h2>
              <Button
                variant="ghost"
                aria-label={t("Adjust markup and discount")}
                title={t("Markup & discount")}
                onClick={() => setDetails(true)}
              >
                <Settings2 size={16} aria-hidden="true" />
              </Button>
            </div>
            <details className="summary-breakdown">
              <summary>
                {t("Zone breakdown")}
                <span>{zones.length}</span>
              </summary>
              <div className="summary-rows">
                {zones.map((z) => (
                  <div key={z.id}>
                    <span title={z.label}>{z.label}</span>
                    <strong>
                      {pricingPending(z)
                        ? t("Pricing pending")
                        : money(z.subtotal)}
                    </strong>
                  </div>
                ))}
              </div>
            </details>
            {Number(estimate.markup_pct) ? (
              <div className="summary-adjustment">
                <span>
                  {t("Markup")} {Number(estimate.markup_pct)}%
                </span>
                <span>{money(marked - subtotal)}</span>
              </div>
            ) : null}
            {Number(estimate.discount_pct) ? (
              <div className="summary-adjustment">
                <span>
                  {t("Discount")} {Number(estimate.discount_pct)}%
                </span>
                <span>−{money(discount)}</span>
              </div>
            ) : null}
            <div className="grand-total">
              <span>{t("Grand total")}</span>
              <strong>{money(total)}</strong>
            </div>
            {pendingZoneCount ? (
              <p className="pending-scope-note">
                {t("Zones with unconfirmed pricing: {0}.", pendingZoneCount)}
              </p>
            ) : null}
            {pdfMode === "pre" ? (
              <p className="summary-note">
                {t("Pre-estimate PDF range")}
                <br />
                {money(total * 0.9)} – {money(total * 1.15)}
              </p>
            ) : null}
            {pdfMode === "final" ? (
              <PdfChecks checks={finalChecks.data} />
            ) : null}
            <Button
              className="full-width"
              variant="primary"
              onClick={() => setProposal(true)}
              disabled={busy}
            >
              <Eye size={16} aria-hidden="true" />
              {pdfMode === "pre"
                ? t("Preview Pre-estimate")
                : t("Preview Final Estimate")}
            </Button>
            <Button
              className="full-width"
              busy={exporting === "pdf"}
              disabled={!!exporting || busy}
              onClick={() => exportFile("pdf")}
            >
              <Download size={16} />
              {pdfMode === "pre"
                ? t("Download estimate PDF")
                : t("Download Final PDF")}
            </Button>
            <Button
              className="full-width"
              busy={exporting === "xlsx"}
              disabled={!!exporting || busy}
              onClick={() => exportFile("xlsx")}
            >
              <FileSpreadsheet size={16} />
              {t("Project passport (XLSX)")}
            </Button>
          </section>
        </aside>
      </div>
      {proposal ? (
        <EstimatePdfPreview
          key={`${estimate.id}:${pdfMode}:${pdfRevision}`}
          mode={pdfMode}
          filename={pdfFilename}
          loadPdf={loadPdf}
          checks={pdfMode === "final" ? finalChecks.data : undefined}
          onClose={() => setProposal(false)}
        />
      ) : null}
      {details ? (
        <EstimateForm
          estimate={estimate}
          onClose={() => setDetails(false)}
          onSave={async (data) => {
            await patch(`/estimates/${id}`, data);
            await refresh();
            notify("Estimate details saved");
          }}
        />
      ) : null}
      {zoneForm ? (
        <ZoneForm
          zone={zoneForm === "edit" ? zone : undefined}
          count={zones.length}
          onClose={() => setZoneForm(null)}
          onSave={async (data) => {
            const saved =
              zoneForm === "edit" && zone
                ? await patch<Zone>(`/estimates/${id}/zones/${zone.id}`, data)
                : await post<Zone>(`/estimates/${id}/zones`, data);
            await refresh();
            selectZone(saved.id);
            setPanel("estimate");
            notify("Zone saved");
          }}
        />
      ) : null}
      {adding && zone ? (
        <AddItems
          zone={zone}
          initial={adding}
          onClose={() => setAdding(null)}
          onAdd={addItems}
        />
      ) : null}
      {ai && zone ? (
        <AiInput
          estimateId={estimate.id}
          zoneId={zone.id}
          onClose={() => setAi(false)}
          onApplied={refresh}
        />
      ) : null}
      {deletingZone ? (
        <Confirm
          title={t("Delete this zone?")}
          action={t("Delete zone")}
          busy={busy}
          onClose={() => setDeletingZone(null)}
          onConfirm={() =>
            mutate(async () => {
              await remove(`/estimates/${id}/zones/${deletingZone.id}`);
              setDeletingZone(null);
            }, "Zone deleted")
          }
        >
          {t(
            "“{0}” and its line items will be permanently removed. This cannot be restored from Trash.",
            deletingZone.label,
          )}
        </Confirm>
      ) : null}
      {deletingItem ? (
        <Confirm
          title={t("Remove this line item?")}
          action={t("Remove item")}
          busy={busy}
          onClose={() => setDeletingItem(null)}
          onConfirm={() =>
            mutate(async () => {
              await remove(`/estimates/${id}/line-items/${deletingItem.id}`);
              setDeletingItem(null);
            }, "Line item removed")
          }
        >
          {t("“{0}” will be removed from this zone.", deletingItem.name)}
        </Confirm>
      ) : null}
    </div>
  );
}
