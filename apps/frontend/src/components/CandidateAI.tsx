import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ScanText, Copy, Check, MessageSquare, Pencil } from "lucide-react";
import { patch, errorMessage } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { Button, ErrorNotice, useNotice } from "./ui";

import {
  loadCandidateReview,
  type ReviewResult as Result,
  type Evidence,
} from "../lib/hrReview";
import { outreachLine, copyOutreach } from "../lib/outreachRich";
import { useHRLocalization } from "../lib/hrLocalization";
export default function CandidateAI({
  id,
  active = true,
}: {
  id: string;
  active?: boolean;
}) {
  const { t, language } = useI18n();
  const notify = useNotice();
  const client = useQueryClient();
  const key = ["hr-ai", id];
  const query = useQuery({
    queryKey: key,
    queryFn: () => loadCandidateReview(id),
    enabled: active,
    retry: false,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    refetchInterval: (query) =>
      query.state.status === "error" ? false : 30_000,
  });
  const [editingMessage, setEditingMessage] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [edited, setEdited] = useState<{
    text: string;
    version: string;
    language: string;
  } | null>(null);
  const review = query.data?.review;
  const busy = query.isFetching && (!review || review.stale);
  const localization = useHRLocalization(
    { scope: "candidate", candidate_id: id },
    review
      ? [
          review.content.summary,
          review.content.experience,
          ...[...review.content.strengths, ...review.content.gaps].flatMap(
            (p) => [p.text, p.question, p.answer],
          ),
          ...review.content.interview_questions,
          ...(review.message_draft_en ? [] : [review.message_draft]),
        ]
      : [],
    active && !!review && !busy,
  );
  const tr = localization.display;
  const savedMessage = review
    ? language === "en"
      ? review.message_draft_en || tr(review.message_draft)
      : review.message_draft
    : "";
  const currentEdit = edited?.language === language ? edited : null;
  const message = currentEdit?.text ?? savedMessage;
  const dirty = !!review && message !== savedMessage;
  const translating = language === "en" && localization.translating;
  useEffect(() => {
    setEditingMessage(false);
  }, [language]);
  async function saveMessage() {
    if (!review || saving || busy || !dirty) return;
    setSaving(true);
    setError("");
    try {
      const result = await patch<Result>(`/hr/candidates/${id}/ai/message`, {
        message,
        expected_updated_at: currentEdit?.version ?? review.updated_at,
        language: language === "en" ? "en" : "original",
      });
      client.setQueryData(key, result);
      setEdited(null);
      setEditingMessage(false);
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
            <ScanText size={18} />
            {t("Application review")}
          </h3>
        </div>
      </header>
      {query.isPending ? (
        <p role="status" className="hr-muted">
          {t("Preparing review…")}
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
      {busy && !query.isPending && (
        <p role="status" className="hr-muted">
          {t("Checking professional answers and preparing a message…")}
        </p>
      )}
      {error && <ErrorNotice>{t(error)}</ErrorNotice>}
      {translating && (
        <p role="status" className="hr-muted">
          {t("Translating HR content…")}
        </p>
      )}
      {language === "en" && localization.isError && (
        <ErrorNotice retry={() => void localization.refetch()}>
          {t("Could not translate the HR content. Please try again.")}
        </ErrorNotice>
      )}
      {review &&
        !translating &&
        !(language === "en" && localization.isError) && (
          <>
            {review.stale && (
              <p className="hr-ai-stale" role="status">
                {t(
                  "Updating the review for changed application or job requirements…",
                )}
              </p>
            )}
            <div className="hr-ai-overview">
              <p>{tr(review.content.summary)}</p>
              <h4>{t("Experience from the application")}</h4>
              <p>{tr(review.content.experience)}</p>
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
                          <p>{tr(point.text)}</p>
                          <details>
                            <summary>{t("Application evidence")}</summary>
                            <p className="hr-muted">{tr(point.question)}</p>
                            <blockquote>{tr(point.answer)}</blockquote>
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
                  <li key={i}>{tr(q)}</li>
                ))}
              </ol>
            </section>
            <section className="hr-ai-message">
              <h4>
                <MessageSquare size={17} />
                {t("Message to the candidate")}
              </h4>
              {editingMessage ? (
                <textarea
                  aria-label={t("Recruiter message")}
                  value={message}
                  onChange={(e) =>
                    setEdited({
                      text: e.target.value,
                      version: currentEdit?.version ?? review.updated_at,
                      language,
                    })
                  }
                  maxLength={6000}
                  rows={9}
                  disabled={saving || busy}
                />
              ) : (
                <div
                  className="hr-message-preview"
                  role="document"
                  aria-label={t("Recruiter message preview")}
                  tabIndex={0}
                >
                  {message.split("\n").map((line, i) => {
                    const { heading, rest } = outreachLine(line);
                    return (
                      <div key={i}>
                        {heading && <strong>{heading}</strong>}
                        {rest || (!heading ? "\u00a0" : "")}
                      </div>
                    );
                  })}
                </div>
              )}
              <div className="hr-ai-message-actions">
                <div className="button-row">
                  {!editingMessage && (
                    <Button
                      onClick={() => setEditingMessage(true)}
                      disabled={busy || translating}
                    >
                      <Pencil size={16} />
                      {t("Edit message")}
                    </Button>
                  )}
                  {editingMessage && (
                    <Button
                      onClick={() => void saveMessage()}
                      busy={saving}
                      disabled={!dirty || busy || !message.trim()}
                    >
                      <Check size={16} />
                      {t("Save message")}
                    </Button>
                  )}
                  <Button
                    variant="primary"
                    disabled={!message.trim() || translating}
                    onClick={async () => {
                      try {
                        const format = await copyOutreach(message);
                        notify(
                          t(
                            format === "rich"
                              ? "Message copied with formatting"
                              : "Message copied as plain text",
                          ),
                        );
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
                  {t("You have unsaved message changes.")}
                </p>
              )}
            </section>
          </>
        )}
    </section>
  );
}
