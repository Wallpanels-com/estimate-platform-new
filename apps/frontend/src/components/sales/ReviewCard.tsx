import { useState } from "react";
import { CheckCircle2, AlertTriangle, Lightbulb } from "lucide-react";
import type { Review } from "./types";
import { useSalesText, when } from "./shared";
export default function ReviewCard({
  review,
  onContact,
}: {
  review: Review;
  onContact?: (id: string) => void;
}) {
  const s = useSalesText();
  const [expanded, setExpanded] = useState(false);
  const labels: Record<string, string> = {
    no_significant_issues: s(
      "Существенных ошибок не найдено",
      "No significant issues found",
    ),
    review_needed: s("Требует проверки", "Needs review"),
    insufficient_evidence: s("Недостаточно данных", "Insufficient evidence"),
  };
  return (
    <article className="sales-review">
      <div className="sales-row">
        <span
          className={
            "sales-badge " +
            (review.outcome === "review_needed" ? "concern" : "positive")
          }
        >
          {labels[review.outcome] || review.outcome}
        </span>
        <time>{when(review.created_at)}</time>
      </div>
      {review.contact_name && <h2>{review.contact_name}</h2>}
      <p className="sales-review-summary">{review.summary}</p>
      <small>
        {s(
          "Предварительный разбор Groq · не подтверждён человеком",
          "Preliminary Groq review · not human verified",
        )}
      </small>
      <div className="sales-findings">
        {review.findings.map((f, i) => (
          <section key={i} className={"sales-finding " + f.kind}>
            <strong>
              {f.kind === "strength" ? (
                <CheckCircle2 size={16} />
              ) : f.kind === "issue" ? (
                <AlertTriangle size={16} />
              ) : (
                <Lightbulb size={16} />
              )}
              {f.kind === "strength"
                ? s("Хорошо", "Strength")
                : f.kind === "issue"
                  ? s("Проверить", "Check")
                  : s("Можно улучшить", "Suggestion")}
            </strong>
            <blockquote>{f.quote}</blockquote>
            <p>{f.explanation}</p>
            {f.recommendation && (
              <p className="sales-muted">{f.recommendation}</p>
            )}
          </section>
        ))}
      </div>
      {!!review.next_steps.length && (
        <ul>
          {review.next_steps.map((v, i) => (
            <li key={i}>{v}</li>
          ))}
        </ul>
      )}
      {!!review.limitations.length && (
        <p className="sales-muted">{review.limitations.join(" ")}</p>
      )}
      <div className="sales-row">
        <button
          className="sales-text-button"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
        >
          {expanded
            ? s("Скрыть первоисточник", "Hide source")
            : s("Первоисточник с подсветкой", "Highlighted source")}
        </button>
        {onContact && review.contact_id && (
          <button
            className="sales-text-button"
            onClick={() => onContact(review.contact_id!)}
          >
            {s("Открыть клиента", "Open client")} →
          </button>
        )}
      </div>
      {expanded && (
        <div className="sales-source">
          {review.sources.map((source) => {
            const candidates = review.findings
              .filter((f) => f.source_id === source.id)
              .map((f) => ({ ...f, start: source.text.indexOf(f.quote) }))
              .filter((f) => f.start >= 0)
              .sort((a, b) => a.start - b.start);
            const spans: React.ReactNode[] = [];
            let end = 0;
            candidates.forEach((f, i) => {
              if (f.start < end) return;
              spans.push(source.text.slice(end, f.start));
              spans.push(
                <mark key={i} className={f.kind} title={f.explanation}>
                  {f.quote}
                </mark>,
              );
              end = f.start + f.quote.length;
            });
            spans.push(source.text.slice(end));
            return (
              <section key={source.id}>
                <small>
                  {source.actor}
                  {source.start_ms != null
                    ? ` · ${Math.floor(source.start_ms / 60000)}:${String(Math.floor(source.start_ms / 1000) % 60).padStart(2, "0")}`
                    : ""}{" "}
                  · {when(source.date)}
                </small>
                <p>{spans}</p>
              </section>
            );
          })}
        </div>
      )}
    </article>
  );
}
