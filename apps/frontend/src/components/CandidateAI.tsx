import { useState } from "react";
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
  } | null>(null);
  const review = query.data?.review;
  const busy = query.isFetching && (!review || review.stale);
  const message = edited?.text ?? review?.message_draft ?? "";
  const dirty = !!review && message !== review.message_draft;
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
          {t(
            "Checking professional answers and preparing a Ukrainian message…",
          )}
        </p>
      )}
      {error && <ErrorNotice>{t(error)}</ErrorNotice>}
      {review && (
        <>
          {review.stale && (
            <p className="hr-ai-stale" role="status">
              {t(
                "Updating the review for changed application or job requirements…",
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
            {editingMessage ? (
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
                    disabled={busy}
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
                  disabled={!message.trim()}
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
