import type { ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./ui";
import { useI18n } from "../lib/i18n";

export function pageNumbers(
  current: number,
  total: number,
): (number | string)[] {
  const visible = new Set([1, total]);
  for (let n = Math.max(1, current - 1); n <= Math.min(total, current + 1); n++)
    visible.add(n);
  if (current <= 3)
    for (let n = 1; n <= Math.min(5, total); n++) visible.add(n);
  if (current >= total - 2)
    for (let n = Math.max(1, total - 4); n <= total; n++) visible.add(n);
  const pages = [...visible].sort((a, b) => a - b);
  return pages.flatMap((n, i) =>
    i && n - pages[i - 1] > 1
      ? [n - pages[i - 1] === 2 ? n - 1 : `gap-${n}`, n]
      : [n],
  );
}

export default function HRPagination({
  page,
  pageSize,
  total,
  onChange,
  sizeControl,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
  sizeControl?: ReactNode;
}) {
  const { t } = useI18n();
  const last = Math.max(1, Math.ceil(total / pageSize));
  return (
    <footer className="hr-pagination">
      <span className="hr-page-range" aria-live="polite">
        {t(
          "{0}–{1} of {2} candidates",
          total ? (page - 1) * pageSize + 1 : 0,
          Math.min(page * pageSize, total),
          total,
        )}
      </span>
      {sizeControl}
      <nav aria-label={t("Candidate pages")}>
        <Button
          disabled={page <= 1}
          aria-label={t("Previous page")}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft size={17} />
        </Button>
        {pageNumbers(page, last).map((n) =>
          typeof n === "number" ? (
            <Button
              key={n}
              variant={page === n ? "primary" : "ghost"}
              aria-label={t("Page {0}", n)}
              aria-current={page === n ? "page" : undefined}
              onClick={() => onChange(n)}
            >
              {n}
            </Button>
          ) : (
            <span className="hr-page-gap" key={n} aria-hidden="true">
              …
            </span>
          ),
        )}
        <Button
          disabled={page >= last}
          aria-label={t("Next page")}
          onClick={() => onChange(page + 1)}
        >
          <ChevronRight size={17} />
        </Button>
      </nav>
    </footer>
  );
}
