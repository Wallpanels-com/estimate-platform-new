import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { request, API_ORIGIN, TOKEN_KEY, errorMessage } from "../../lib/api";
import { tokenStorage } from "../../lib/portal";
import { Modal, Button, ErrorNotice, Loading } from "../ui";
import type { ContactDetail, Lookups, GhlRecord } from "./types";
import { useSalesText, when, userName, stageName, Blank } from "./shared";
import ReviewCard from "./ReviewCard";

function Recording({ id }: { id: string }) {
  const s = useSalesText();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );
  async function load() {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(
        `${API_ORIGIN}/api/v1/sales/recordings/${encodeURIComponent(id)}`,
        {
          headers: {
            Authorization: `Bearer ${tokenStorage.getItem(TOKEN_KEY)}`,
          },
          signal: AbortSignal.timeout(30000),
        },
      );
      if (!r.ok)
        throw new Error(
          s("Запись недоступна через API", "Recording unavailable through API"),
        );
      setUrl(URL.createObjectURL(await r.blob()));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="sales-recording">
      {url ? (
        <audio controls src={url} />
      ) : (
        <Button variant="secondary" disabled={loading} onClick={load}>
          {loading
            ? s("Загрузка…", "Loading…")
            : s("Слушать запись", "Play recording")}
        </Button>
      )}
      {error && <small role="status">{error}</small>}
    </div>
  );
}
function Message({ m, lookups }: { m: GhlRecord; lookups?: Lookups }) {
  const s = useSalesText();
  const internal = (m.messageType || "").toUpperCase().includes("INTERNAL");
  return (
    <article className={"sales-message " + (internal ? "internal" : "")}>
      <div className="sales-row">
        <strong>
          {internal
            ? s("Внутренний комментарий", "Internal comment")
            : m.messageType?.replace("TYPE_", "") || s("Сообщение", "Message")}
        </strong>
        <time>{when(m.dateAdded)}</time>
      </div>
      <small>
        {m.userId
          ? userName(lookups, m.userId)
          : m.direction === "inbound"
            ? s("Клиент", "Client")
            : m.source || s("Автор не указан", "Author unavailable")}
      </small>
      <p>{(m.body || "").replace(/<[^>]+>/g, " ") || m.status || "—"}</p>
      {m.messageType === "TYPE_CALL" && <Recording id={m._id} />}
    </article>
  );
}
export default function ContactPanel({
  id,
  onClose,
  lookups,
}: {
  id: string;
  onClose: () => void;
  lookups?: Lookups;
}) {
  const s = useSalesText();
  const [tab, setTab] = useState("history");
  const data = useQuery({
    queryKey: ["sales", "contact", id],
    queryFn: ({ signal }) =>
      request<ContactDetail>(`/sales/contacts/${encodeURIComponent(id)}`, {
        signal,
      }),
    refetchInterval: 10000,
  });
  const d = data.data;
  const c = d?.contact;
  const fallback = d?.conversations[0];
  const name =
    c?.fullName ||
    [c?.firstName, c?.lastName].filter(Boolean).join(" ") ||
    fallback?.contactName ||
    fallback?.fullName ||
    d?.opportunities[0]?.contact?.name ||
    s("Карточка клиента", "Client details");
  const tabs = [
    ["history", s("История", "History")],
    ["calls", s("Звонки и транскрипты", "Calls & transcripts")],
    ["analysis", s("Разбор ИИ", "AI review")],
    ["deals", s("Сделки и задачи", "Deals & tasks")],
  ];
  return (
    <Modal title={name} onClose={onClose} wide className="sales-contact-modal">
      <div className="modal-body">
        {data.isLoading ? (
          <Loading />
        ) : data.error ? (
          <ErrorNotice>{errorMessage(data.error)}</ErrorNotice>
        ) : (
          d && (
            <>
              <div className="sales-contact-meta">
                <span>{c?.phone || fallback?.phone || "—"}</span>
                <span>{c?.email || fallback?.email || "—"}</span>
                <span>
                  {s("Ответственный", "Owner")}:{" "}
                  {userName(lookups, c?.assignedTo || fallback?.assignedTo)}
                </span>
                <span>
                  {s("Источник", "Source")}: {c?.source || "—"}
                </span>
              </div>
              {!!c?.attributionSource && (
                <details>
                  <summary>
                    {s("Атрибуция из GHL", "Attribution from GHL")}
                  </summary>
                  <pre>{JSON.stringify(c.attributionSource, null, 2)}</pre>
                </details>
              )}
              <p className="sales-muted">
                {s("Общение за последние", "Communication from the last")}{" "}
                {d.history_days}{" "}
                {s(
                  "дней. В ленте до 500 последних сообщений.",
                  "days. Up to 500 latest messages shown.",
                )}{" "}
                {d.pending > 0
                  ? s(
                      "Данные дополняются в фоне…",
                      "Loading more data in the background…",
                    )
                  : ""}
              </p>
              {d.warning && <ErrorNotice>{d.warning}</ErrorNotice>}
              <nav
                className="sales-tabs"
                aria-label={s("Данные клиента", "Client information")}
              >
                {tabs.map(([key, label]) => (
                  <button
                    key={key}
                    aria-current={tab === key ? "page" : undefined}
                    onClick={() => setTab(key)}
                  >
                    {label}
                    {key === "analysis" && ` · ${d.analyses.length}`}
                  </button>
                ))}
              </nav>
              {tab === "history" && (
                <div className="sales-timeline">
                  {!d.messages.length && !d.notes.length ? (
                    <Blank>
                      {s(
                        "История ещё не загружена или отсутствует в GHL",
                        "History is loading or unavailable in GHL",
                      )}
                    </Blank>
                  ) : (
                    <>
                      {d.notes.map((m) => (
                        <Message
                          key={"note" + m._id}
                          m={{ ...m, messageType: "TYPE_INTERNAL_NOTE" }}
                          lookups={lookups}
                        />
                      ))}
                      {d.messages.map((m) => (
                        <Message key={m._id} m={m} lookups={lookups} />
                      ))}
                    </>
                  )}
                </div>
              )}
              {tab === "calls" && (
                <div className="sales-timeline">
                  {!d.calls.length && !d.transcripts.length && (
                    <Blank>
                      {s(
                        "Транскрипты ещё не загружены или недоступны. Записи звонков — во вкладке «История».",
                        "Transcripts are loading or unavailable. Call recordings are in History.",
                      )}
                    </Blank>
                  )}
                  {d.calls.map((call) => (
                    <article className="sales-message" key={call._id}>
                      <div className="sales-row">
                        <strong>
                          Voice AI ·{" "}
                          {lookups?.agents.find((a) => a.id === call.agentId)
                            ?.name || call.agentId}
                        </strong>
                        <time>{when(call.createdAt)}</time>
                      </div>
                      <p>{call.summary}</p>
                      {call.messageId && <Recording id={call.messageId} />}
                      <details>
                        <summary>
                          {s("Транскрипт GHL", "GHL transcript")} ·{" "}
                          {call.duration || 0}s
                        </summary>
                        <p className="sales-transcript">
                          {call.transcript ||
                            s(
                              "Транскрипт отсутствует",
                              "Transcript unavailable",
                            )}
                        </p>
                      </details>
                    </article>
                  ))}
                  {d.transcripts.map((r) => (
                    <article className="sales-message" key={r._id}>
                      <strong>
                        {s("Транскрипт звонка", "Call transcript")}
                      </strong>
                      {r.availability === "not_available" ? (
                        <p>
                          {s(
                            "GHL пока не предоставляет транскрипт этого звонка",
                            "GHL does not currently provide a transcript for this call",
                          )}
                        </p>
                      ) : (
                        r.segments?.map((seg, i) => (
                          <p key={i}>
                            <small>
                              {seg.startTime != null
                                ? `${Math.floor(seg.startTime / 1000)}s · `
                                : ""}
                              {s("Канал", "Channel")} {seg.mediaChannel ?? "—"}
                            </small>
                            <br />
                            {seg.transcript || seg.text}
                          </p>
                        ))
                      )}
                    </article>
                  ))}
                </div>
              )}
              {tab === "analysis" && (
                <div className="sales-timeline">
                  <p className="sales-muted">
                    {s(
                      "Регламент Sales Ops пока не подключён. Рекомендации ИИ требуют проверки.",
                      "Sales Ops policy has not been supplied. AI suggestions need review.",
                    )}
                  </p>
                  {d.analyses.length ? (
                    d.analyses.map((r) => <ReviewCard key={r.id} review={r} />)
                  ) : (
                    <Blank>
                      {s(
                        "Разбор появится после загрузки текста и обработки очереди Groq",
                        "Review appears after text is loaded and the Groq queue is processed",
                      )}
                    </Blank>
                  )}
                </div>
              )}
              {tab === "deals" && (
                <div className="sales-timeline">
                  {d.opportunities.map((o) => (
                    <article className="sales-message" key={o._id}>
                      <strong>{o.name}</strong>
                      <p>
                        {stageName(lookups, o.pipelineStageId)} · {o.status} ·{" "}
                        {userName(lookups, o.assignedTo)}
                      </p>
                      <small>
                        {s("Обновлено в GHL", "Updated in GHL")}:{" "}
                        {when(o.updatedAt)}
                      </small>
                    </article>
                  ))}
                  {d.tasks.map((t) => (
                    <article className="sales-message" key={t._id}>
                      <strong>{t.title}</strong>
                      <p>{t.body}</p>
                      <span className="sales-badge">
                        {t.completed
                          ? s("Выполнено", "Completed")
                          : s("Не выполнено", "Not completed")}
                      </span>
                    </article>
                  ))}
                </div>
              )}
            </>
          )
        )}
      </div>
    </Modal>
  );
}
