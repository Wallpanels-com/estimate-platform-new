import { useI18n } from "../../lib/i18n";
import type { Lookups } from "./types";
import { Button } from "../ui";
export function useSalesText() {
  const { language } = useI18n();
  return (ru: string, en: string) => (language === "ru" ? ru : en);
}
export function when(value?: string | number | null) {
  if (!value) return "—";
  const d = new Date(
    typeof value === "string" && /^\d+$/.test(value) ? Number(value) : value,
  );
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
}
export function userName(data: Lookups | undefined, id?: string) {
  if (!id) return "—";
  const u = data?.users.find((x) => x.id === id);
  return u ? u.name + (u.deleted ? " · inactive" : "") : id;
}
export function stageName(data: Lookups | undefined, id?: string) {
  return (
    data?.pipelines.flatMap((p) => p.stages).find((x) => x.id === id)?.name ||
    id ||
    "—"
  );
}
export function Pagination({
  page,
  total,
  limit,
  onPage,
}: {
  page: number;
  total: number;
  limit: number;
  onPage: (n: number) => void;
}) {
  const s = useSalesText();
  const pages = Math.max(1, Math.ceil(total / limit));
  return (
    <div className="sales-pagination">
      <span>
        {total.toLocaleString()} {s("записей", "records")} · {page} / {pages}
      </span>
      <div>
        <Button
          variant="secondary"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          {s("Назад", "Previous")}
        </Button>
        <Button
          variant="secondary"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          {s("Далее", "Next")}
        </Button>
      </div>
    </div>
  );
}
export function Blank({ children }: { children: React.ReactNode }) {
  return (
    <div className="sales-blank" role="status">
      {children}
    </div>
  );
}
