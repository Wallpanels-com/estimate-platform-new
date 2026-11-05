import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Copy, RefreshCw, Check, MessageSquare } from "lucide-react";
import { request, post, patch, errorMessage } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { Button, ErrorNotice, useNotice } from "./ui";

type Evidence = { text: string; question: string; answer: string };
type Review = {
  content: {
    summary: string;
    experience: string;
    strengths: Evidence[];
    gaps: Evidence[];
    interview_questions: string[];
    message_uk: string;
  };
  message_draft: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  stale: boolean;
};
type Result = { enabled: boolean; review: Review | null };
export default function CandidateAI({ id }: { id: string }) {
  const { t, language } = useI18n();
  const notify = useNotice();
  const client = useQueryClient();
  const key = ["hr-ai", id];
  const query = useQuery({
    queryKey: key,
    queryFn: () => request<Result>(`/hr/candidates/${id}/ai`),
    retry: false,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [edited, setEdited] = useState<{
    text: string;
    version: string;
  } | null>(null);
  const review = query.data?.review;
  const message = edited?.text ?? review?.message_draft ?? "";
  const dirty = !!review && message !== review.message_draft;
  async function generate() {
    if (busy || saving || dirty) return;
    setBusy(true);
    setError("");
    try {
      const result = await post<Result>(`/hr/candidates/${id}/ai`, {
        refresh: !!review && !review.stale,
      });
      client.setQueryData(key, result);
      setEdited(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function saveMessage() {
    if (!review || saving || busy || !dirty) return;
    setSaving(true);
    setError("");
    try {
      const result = await patch<Result>(`/hr/candidates/${id}/ai/message`, {
        message,
        expected_updated_at: edited?.version ?? review.updated_at,
      });
      client.setQueryData(key, result);
      setEdited(null);
      notify(t("Message saved"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSaving(false);
    }
  }
  return (
    <section className="hr-ai" aria-labelledby={`ai-${id}`} aria-busy={busy}>
      <header className="hr-ai-heading">
        <div>
          <h3 id={`ai-${id}`}>
            <Sparkles size={18} />
            {t("AI application review")}
          </h3>
          <p>
            {t(
              "Evidence from the application. The recruiter makes the decision.",
            )}
          </p>
        </div>
        <Button
          onClick={() => void generate()}
          busy={busy}
          disabled={!query.data?.enabled || saving || dirty}
          variant={review ? "ghost" : "primary"}
        >
          {review ? <RefreshCw size={16} /> : <Sparkles size={16} />}
          {t(
            busy
              ? "Preparing review…"
              : review
                ? "Refresh review"
                : "Analyze application",
          )}
        </Button>
      </header>
      {query.isPending ? (
        <p role="status" className="hr-muted">
          {t("Loading saved review…")}
        </p>
      ) : query.isError ? (
        <ErrorNotice retry={() => void query.refetch()}>
          {errorMessage(query.error)}
        </ErrorNotice>
      ) : !query.data?.enabled ? (
        <p className="hr-muted">
          {t("HR AI is not configured. Contact Dmitry.")}
        </p>
      ) : null}
      {busy && (
        <p role="status" className="hr-muted">
          {t(
            "Checking professional answers and preparing a Ukrainian message…",
          )}
        </p>
      )}
      {error && <ErrorNotice>{t(error)}</ErrorNotice>}
      {!review && !query.isPending && !query.isError && (
        <p className="hr-muted">
          {t(
            "Only professional answers and vacancy requirements are sent to Groq. Phone, email and HR notes are excluded. Analysis runs only when requested.",
          )}
        </p>
      )}
      {review && (
        <>
          {review.stale && (
            <p className="hr-ai-stale" role="status">
              {t(
                "The application or job requirements changed. Refresh the review before using it.",
              )}
            </p>
          )}
          <div className="hr-ai-overview">
            <p>{review.content.summary}</p>
            <h4>{t("Experience from the application")}</h4>
            <p>{review.content.experience}</p>
          </div>
          <div className="hr-ai-evidence-grid">
            {(
              [
                ["Supported strengths", review.content.strengths],
                ["Limitations stated by the candidate", review.content.gaps],
              ] as [string, Evidence[]][]
            ).map(([title, points]) => (
              <section key={title}>
                <h4>{t(title)}</h4>
                {points.length ? (
                  <ul>
                    {points.map((point, i) => (
                      <li key={i}>
                        <p>{point.text}</p>
                        <details>
                          <summary>{t("Application evidence")}</summary>
                          <p className="hr-muted">{point.question}</p>
                          <blockquote>{point.answer}</blockquote>
                        </details>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="hr-muted">
                    {t("Not established by the available answers.")}
                  </p>
                )}
              </section>
            ))}
          </div>
          <section className="hr-ai-questions">
            <h4>{t("Questions for the interview")}</h4>
            <ol>
              {review.content.interview_questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ol>
          </section>
          <section className="hr-ai-message">
            <h4>
              <MessageSquare size={17} />
              {t("First contact · Ukrainian")}
            </h4>
            <textarea
              aria-label={t("Recruiter message")}
              value={message}
              onChange={(e) =>
                setEdited({
                  text: e.target.value,
                  version: edited?.version ?? review.updated_at,
                })
              }
              maxLength={6000}
              rows={9}
              disabled={saving || busy}
            />
            <div className="hr-ai-message-actions">
              <small>
                {t(
                  "Review and edit before sending. Nothing is sent automatically.",
                )}
              </small>
              <div className="button-row">
                <Button
                  onClick={() => void saveMessage()}
                  busy={saving}
                  disabled={!dirty || busy || !message.trim()}
                >
                  <Check size={16} />
                  {t("Save message")}
                </Button>
                <Button
                  variant="primary"
                  disabled={!message.trim()}
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(message);
                      notify(t("Message copied"));
                    } catch {
                      setError(
                        t(
                          "Could not copy. Select and copy the message manually.",
                        ),
                      );
                    }
                  }}
                >
                  <Copy size={16} />
                  {t("Copy message")}
                </Button>
              </div>
            </div>
            {dirty && (
              <p role="status" className="hr-muted">
                {t(
                  "You have unsaved message changes. Save them before refreshing the review.",
                )}
              </p>
            )}
          </section>
          <small className="hr-ai-meta">
            {new Date(review.created_at).toLocaleString(
              language === "ru" ? "ru-RU" : "en-US",
            )}{" "}
            · {review.created_by}
          </small>
        </>
      )}
    </section>
  );
}
