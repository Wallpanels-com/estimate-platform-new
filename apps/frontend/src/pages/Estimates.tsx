import Select from "../components/Select";
import { useI18n } from "../lib/i18n";
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Search,
  Copy,
  Trash2,
  RotateCcw,
  ArrowUpRight,
  WandSparkles,
  SlidersHorizontal,
} from "lucide-react";
import {
  request,
  post,
  remove,
  money,
  dateLabel,
  errorMessage,
} from "../lib/api";
import type { Estimate, EstimateSummary } from "../lib/types";
import {
  Button,
  Field,
  Confirm,
  EmptyState,
  ErrorNotice,
  Loading,
  PageHeader,
  useNotice,
} from "../components/ui";
import EstimateForm from "../components/EstimateForm";
import NewEstimateButton, {
  type NewEstimateType,
} from "../components/NewEstimateButton";
export default function Estimates({ trash = false }: { trash?: boolean }) {
  const { t, n } = useI18n();

  const navigate = useNavigate();
  const client = useQueryClient();
  const notify = useNotice();
  const [params, setParams] = useSearchParams();
  const search = params.get("q") || "";
  const type = params.get("type") || "all";
  const [create, setCreate] = useState<NewEstimateType | null>(null);
  const [deleting, setDeleting] = useState<EstimateSummary | null>(null);
  const data = useQuery({
    queryKey: ["estimates", trash],
    queryFn: ({ signal }) =>
      request<EstimateSummary[]>(trash ? "/estimates/trash" : "/estimates", {
        signal,
      }),
  });
  const rows = useMemo(() => {
    const author = params.get("author") || "";
    const from = params.get("from") || "";
    const to = params.get("to") || "";
    const minimum = params.get("min");
    const maximum = params.get("max");
    const sort = params.get("sort") || "updated_desc";
    const result = (data.data || []).filter(
      (e) =>
        (type === "all" || e.type === type) &&
        [e.title, e.client_name, e.created_by].some((v) =>
          v?.toLowerCase().includes(search.toLowerCase()),
        ) &&
        (!author || e.created_by === author || e.updated_by === author) &&
        (!from || e.updated_at.slice(0, 10) >= from) &&
        (!to || e.updated_at.slice(0, 10) <= to) &&
        (!minimum || Number(e.final_total) >= Number(minimum)) &&
        (!maximum || Number(e.final_total) <= Number(maximum)),
    );
    return result.sort((a, b) =>
      sort === "total_asc"
        ? Number(a.final_total) - Number(b.final_total)
        : sort === "total_desc"
          ? Number(b.final_total) - Number(a.final_total)
          : sort === "title"
            ? (a.title || "").localeCompare(b.title || "")
            : sort === "updated_asc"
              ? a.updated_at.localeCompare(b.updated_at)
              : b.updated_at.localeCompare(a.updated_at),
    );
  }, [data.data, type, search, params]);
  const authors = [
    ...new Set(
      (data.data || [])
        .flatMap((e) => [e.created_by, e.updated_by])
        .filter((v): v is string => !!v),
    ),
  ];
  function filter(key: string, value: string) {
    setParams(
      (p) => {
        value ? p.set(key, value) : p.delete(key);
        return p;
      },
      { replace: true },
    );
  }
  const action = useMutation({
    mutationFn: async ({
      id,
      operation,
    }: {
      id: string;
      operation: "delete" | "duplicate" | "restore" | "permanent";
    }) => {
      if (operation === "delete") return remove(`/estimates/${id}`);
      if (operation === "permanent")
        return remove(`/estimates/${id}/permanent`);
      const copy = await post<Estimate>(`/estimates/${id}/${operation}`);
      if (operation === "duplicate") navigate(`/estimates/${copy.id}`);
    },
    onSuccess: (_, v) => {
      client.invalidateQueries({ queryKey: ["estimates"] });
      setDeleting(null);
      notify(
        v.operation === "delete"
          ? "Estimate moved to Trash"
          : v.operation === "restore"
            ? "Estimate restored"
            : v.operation === "permanent"
              ? "Estimate permanently deleted"
              : "Estimate duplicated",
      );
    },
    onError: (e) => notify(errorMessage(e), true),
  });
  return (
    <>
      <PageHeader
        title={trash ? t("Trash") : t("Estimates")}
        description={
          trash
            ? t("Deleted estimates can be restored for 7 days.")
            : t(
                "Project scopes, considered pricing, and client-ready estimates.",
              )
        }
        actions={
          !trash ? (
            <>
              <Link className="button secondary" to="/quick-estimate">
                <WandSparkles size={16} />
                {t("Quick estimate")}
              </Link>
              <NewEstimateButton onSelect={setCreate} />
            </>
          ) : undefined
        }
      />
      <section
        className={`estimate-register ${trash ? "trash-register" : ""}`}
        aria-label={trash ? t("Deleted estimates") : t("Estimate register")}
      >
        <div className="register-toolbar">
          <div className="segments" aria-label={t("Filter estimate type")}>
            {[
              ["all", t("All estimates")],
              ["pre", t("Pre-estimate")],
              ["final", t("Final")],
              ["quick", t("Quick")],
            ].map(([value, label]) => (
              <button
                key={value}
                aria-pressed={type === value}
                onClick={() => filter("type", value === "all" ? "" : value)}
              >
                {label}
              </button>
            ))}
          </div>
          <label className="search-field">
            <Search size={17} aria-hidden="true" />
            <input
              aria-label={t("Search estimates")}
              placeholder={t("Search client or estimate…")}
              value={search}
              onChange={(e) => filter("q", e.target.value)}
              autoComplete="off"
            />
          </label>
          <details className="register-filters">
            <summary>
              <SlidersHorizontal size={16} />
              {t("Filters")}
            </summary>
            <div className="filter-fields">
              <Field label={t("Author")}>
                <Select
                  aria-label={t("Filter by author")}
                  value={params.get("author") || ""}
                  onChange={(e) => filter("author", e.target.value)}
                >
                  <option value="">{t("All authors")}</option>
                  {authors.map((author) => (
                    <option key={author} value={author}>
                      {author}
                    </option>
                  ))}
                </Select>
              </Field>
              <label>
                {t("Updated from")}
                <input
                  aria-label={t("Updated from")}
                  type="date"
                  value={params.get("from") || ""}
                  onChange={(e) => filter("from", e.target.value)}
                />
              </label>
              <label>
                {t("Updated to")}
                <input
                  aria-label={t("Updated to")}
                  type="date"
                  value={params.get("to") || ""}
                  onChange={(e) => filter("to", e.target.value)}
                />
              </label>
              <label>
                {t("Minimum total ($)")}
                <input
                  aria-label={t("Minimum total")}
                  type="number"
                  min="0"
                  value={params.get("min") || ""}
                  onChange={(e) => filter("min", e.target.value)}
                />
              </label>
              <label>
                {t("Maximum total ($)")}
                <input
                  aria-label={t("Maximum total")}
                  type="number"
                  min="0"
                  value={params.get("max") || ""}
                  onChange={(e) => filter("max", e.target.value)}
                />
              </label>
              <Field label={t("Sort by")}>
                <Select
                  aria-label={t("Sort estimates")}
                  value={params.get("sort") || "updated_desc"}
                  onChange={(e) => filter("sort", e.target.value)}
                >
                  <option value="updated_desc">{t("Recently updated")}</option>
                  <option value="updated_asc">{t("Oldest update")}</option>
                  <option value="total_desc">{t("Highest total")}</option>
                  <option value="total_asc">{t("Lowest total")}</option>
                  <option value="title">{t("Title")}</option>
                </Select>
              </Field>
              <Button
                variant="ghost"
                onClick={() => setParams(new URLSearchParams())}
              >
                {t("Clear filters")}
              </Button>
            </div>
          </details>
        </div>
        {data.isLoading ? (
          <Loading />
        ) : data.error ? (
          <ErrorNotice retry={() => data.refetch()}>
            {errorMessage(data.error)}
          </ErrorNotice>
        ) : !rows.length ? (
          <EmptyState
            title={
              search
                ? t("No matching estimates")
                : trash
                  ? t("Trash is empty")
                  : t("Start with your next project")
            }
            action={
              !trash && !search ? (
                <NewEstimateButton onSelect={setCreate} />
              ) : undefined
            }
          >
            {search
              ? t("Try another client name or clear the filters.")
              : trash
                ? t("Deleted estimates will appear here.")
                : t(
                    "Create an estimate, define your zones, and build the scope.",
                  )}
          </EmptyState>
        ) : (
          <div className="register-table">
            <div className="register-table-head">
              <span>{t("Project / client")}</span>
              <span>{t("Type")}</span>
              <span>{t("Updated")}</span>
              <span className="numeric">{t("Base total")}</span>
              <span>{t("Actions")}</span>
            </div>
            {rows.map((e) => (
              <article className="estimate-row" key={e.id}>
                <div className="estimate-name">
                  <Link to={`/estimates/${e.id}`}>
                    {e.title || t("Untitled estimate")}
                    <ArrowUpRight size={16} aria-hidden="true" />
                  </Link>
                  <span>
                    {e.client_name || t("No client")}
                    {e.created_by ? (
                      <span className="creator"> · {e.created_by}</span>
                    ) : null}
                  </span>
                </div>
                <span className={`badge ${e.type}`}>
                  {e.type === "pre"
                    ? t("Pre-estimate")
                    : e.type === "final"
                      ? t("Final")
                      : t("Quick")}
                </span>
                <div className="estimate-date">
                  <time dateTime={e.updated_at}>{dateLabel(e.updated_at)}</time>
                  <small>{t(e.status)}</small>
                </div>
                <strong className="numeric">{money(e.final_total)}</strong>
                <div className="row-actions">
                  {trash ? (
                    <>
                      <Button
                        variant="ghost"
                        onClick={() =>
                          action.mutate({ id: e.id, operation: "restore" })
                        }
                        disabled={action.isPending}
                      >
                        <RotateCcw size={16} />
                        {t("Restore")}
                      </Button>
                      <Button
                        variant="ghost"
                        aria-label={t(
                          "Permanently delete {0}",
                          e.title || t("estimate"),
                        )}
                        title={t("Permanently delete")}
                        onClick={() => setDeleting(e)}
                      >
                        <Trash2 size={16} />
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button
                        variant="ghost"
                        aria-label={t(
                          "Duplicate {0}",
                          e.title || t("estimate"),
                        )}
                        title={t("Duplicate estimate")}
                        onClick={() =>
                          action.mutate({ id: e.id, operation: "duplicate" })
                        }
                        disabled={action.isPending}
                      >
                        <Copy size={16} />
                      </Button>
                      <Button
                        variant="ghost"
                        aria-label={t("Delete {0}", e.title || t("estimate"))}
                        title={t("Move to Trash")}
                        onClick={() => setDeleting(e)}
                      >
                        <Trash2 size={16} />
                      </Button>
                    </>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
        <footer className="register-footer">
          <span>{n(rows.length, "estimates")}</span>
          <span>
            {t("Amounts in USD · Base totals before markup & discount")}
          </span>
        </footer>
      </section>
      {create ? (
        <EstimateForm
          initialType={create}
          onClose={() => setCreate(null)}
          onSave={async (body) => {
            const e = await post<Estimate>("/estimates", body);
            client.invalidateQueries({ queryKey: ["estimates"] });
            navigate(`/estimates/${e.id}`);
          }}
        />
      ) : null}
      {deleting ? (
        <Confirm
          title={
            trash
              ? t("Permanently delete estimate?")
              : t("Move estimate to Trash?")
          }
          action={trash ? t("Permanently delete") : t("Move to Trash")}
          onClose={() => setDeleting(null)}
          busy={action.isPending}
          onConfirm={() =>
            action.mutate({
              id: deleting.id,
              operation: trash ? "permanent" : "delete",
            })
          }
        >
          “{deleting.title || t("Untitled estimate")}”{" "}
          {trash
            ? t(
                "will be permanently deleted with its zones and line items. This cannot be restored.",
              )
            : t("can be restored from Trash for 7 days.")}
        </Confirm>
      ) : null}
    </>
  );
}
