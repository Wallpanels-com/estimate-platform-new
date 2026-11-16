import { Fragment, useLayoutEffect, useRef } from "react";
import {
  ArrowDown,
  ArrowDownLeft,
  ArrowUpRight,
  Phone,
  StickyNote,
  GitBranch,
  CircleDot,
  MessageCircle,
} from "lucide-react";
import type { ContactDetail, GhlRecord, Lookups } from "./types";
import { Blank, useSalesText, userName, when } from "./shared";
import Recording from "./Recording";
import Transcript from "./Transcript";
function transcriptFor(d: ContactDetail, id: string) {
  const voice = d.calls.find((c) => c.messageId === id && c.transcript);
  return voice
    ? {
        ...voice,
        transcript_source: "ghl_voice_ai",
        segments: [{ text: voice.transcript }],
        availability: "available",
      }
    : d.transcripts.find((t) => t._id === id);
}
function CallCard({
  call,
  transcript,
  lookups,
}: {
  call: GhlRecord;
  transcript?: GhlRecord;
  lookups?: Lookups;
}) {
  const s = useSalesText();
  const status = call.meta?.call?.status || call.status;
  const duration = call.meta?.call?.duration ?? call.duration;
  const labels: Record<string, string> = {
    completed: s("Завершён", "Completed"),
    connected: s("Соединение установлено", "Connected"),
    "no-answer": s("Нет ответа", "No answer"),
    busy: s("Занято", "Busy"),
    failed: s("Не удалось соединиться", "Failed"),
    canceled: s("Отменён", "Cancelled"),
    voicemail: s("Голосовая почта", "Voicemail"),
  };
  const incoming = call.direction === "inbound";
  const id = call.messageId || call._id;
  const mayHaveAudio =
    call.messageId ||
    (call.messageType === "TYPE_CALL" &&
      ["completed", "connected", "voicemail"].includes(status || ""));
  return (
    <article className="sales-chat-call">
      <header>
        <Phone size={18} />
        <strong>
          {call.agentId
            ? "Voice AI"
            : incoming
              ? s("Входящий звонок", "Incoming call")
              : s("Исходящий звонок", "Outgoing call")}
        </strong>
        {incoming ? <ArrowDownLeft size={15} /> : <ArrowUpRight size={15} />}
        <time>{when(call.dateAdded || call.createdAt)}</time>
      </header>
      <div className="sales-call-facts">
        <span>
          {labels[status || ""] ||
            status ||
            s("Статус не указан", "Status unavailable")}
        </span>
        {duration != null && (
          <span>
            {Math.floor(duration / 60)}:
            {String(Math.floor(duration) % 60).padStart(2, "0")}
          </span>
        )}
        {call.userId && <span>{userName(lookups, call.userId)}</span>}
      </div>
      {call.summary && <p>{call.summary}</p>}
      {mayHaveAudio ? (
        <>
          <Recording id={id} />
          <Transcript id={id} initial={transcript} />
        </>
      ) : transcript?.segments?.length ? (
        <Transcript id={id} initial={transcript} />
      ) : (
        <small>
          {s(
            "Завершённый разговор не зафиксирован в GHL.",
            "GHL did not record a completed conversation.",
          )}
        </small>
      )}
    </article>
  );
}
export function CallsList({
  detail: d,
  lookups,
}: {
  detail: ContactDetail;
  lookups?: Lookups;
}) {
  const s = useSalesText();
  const messages = d.messages.filter((m) => m.messageType === "TYPE_CALL");
  const known = new Set(messages.map((m) => m._id));
  const calls = [
    ...messages,
    ...d.calls.filter((c) => !c.messageId || !known.has(c.messageId)),
  ].sort(
    (a, b) =>
      new Date(b.dateAdded || b.createdAt || 0).getTime() -
      new Date(a.dateAdded || a.createdAt || 0).getTime(),
  );
  return (
    <div className="sales-calls-list">
      <p className="sales-muted">
        {s(
          "Записи и текст собраны у каждого звонка. Если GHL не создал транскрипт, при открытии текста проверяем аудио и расшифровываем через Groq.",
          "Recordings and text are grouped by call. If GHL has no transcript, opening the text checks the audio and requests a Groq transcription.",
        )}
      </p>
      {calls.length ? (
        calls.map((c) => (
          <CallCard
            key={c._id}
            call={c}
            transcript={
              c.transcript
                ? {
                    ...c,
                    segments: [{ text: c.transcript }],
                    transcript_source: "ghl_voice_ai",
                  }
                : transcriptFor(d, c.messageId || c._id)
            }
            lookups={lookups}
          />
        ))
      ) : (
        <Blank>
          {s(
            "Звонков в загруженной истории нет",
            "No calls in the imported history",
          )}
        </Blank>
      )}
    </div>
  );
}
export default function ChatTimeline({
  detail: d,
  lookups,
  clientName,
}: {
  detail: ContactDetail;
  lookups?: Lookups;
  clientName: string;
}) {
  const s = useSalesText();
  const viewport = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const entries = [
    ...d.messages,
    ...d.notes.map((n) => ({
      ...n,
      _id: "note:" + n._id,
      messageType: "TYPE_INTERNAL_NOTE",
    })),
  ].sort(
    (a, b) =>
      new Date(a.dateAdded || a.createdAt || 0).getTime() -
        new Date(b.dateAdded || b.createdAt || 0).getTime() ||
      a._id.localeCompare(b._id),
  );
  const end = entries.at(-1)?._id;
  useLayoutEffect(() => {
    if (atBottom.current && viewport.current)
      viewport.current.scrollTop = viewport.current.scrollHeight;
  }, [end]);
  let previousDay = "";
  return (
    <div className="sales-chat-shell">
      <div className="sales-chat-toolbar">
        <span>
          <MessageCircle size={15} />
          {s(
            "Клиент слева · Компания справа",
            "Client on the left · Company on the right",
          )}
        </span>
        <button
          type="button"
          onClick={() =>
            viewport.current?.scrollTo({
              top: viewport.current.scrollHeight,
              behavior: "smooth",
            })
          }
        >
          <ArrowDown size={15} />
          {s("К последним", "Latest")}
        </button>
      </div>
      <div
        className="sales-chat-scroll"
        ref={viewport}
        onScroll={() => {
          const el = viewport.current!;
          atBottom.current =
            el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
        tabIndex={0}
        role="region"
        aria-label={s("История переписки", "Conversation history")}
      >
        {!entries.length && (
          <Blank>
            {s(
              "История ещё загружается или отсутствует в GHL",
              "History is loading or unavailable in GHL",
            )}
          </Blank>
        )}
        {entries.map((m) => {
          const date = m.dateAdded || m.createdAt;
          const day = date
            ? new Date(date).toLocaleDateString(s("ru-RU", "en-US"), {
                day: "numeric",
                month: "long",
                year: "numeric",
              })
            : s("Дата не указана", "Date unavailable");
          const separator = day !== previousDay;
          previousDay = day;
          const internal = m.messageType?.includes("INTERNAL");
          const activity = m.messageType?.startsWith("TYPE_ACTIVITY");
          const opportunity = m.messageType === "TYPE_ACTIVITY_OPPORTUNITY";
          const incoming = m.direction === "inbound";
          const text = (m.body || "").replace(/<[^>]+>/g, " ");
          const events: Record<string, string> = {
            "Opportunity updated": s("Сделка обновлена", "Opportunity updated"),
            "Opportunity created": s("Создана сделка", "Opportunity created"),
          };
          return (
            <Fragment key={m._id}>
              {separator && (
                <div className="sales-chat-day">
                  <span>{day}</span>
                </div>
              )}
              {m.messageType === "TYPE_CALL" ? (
                <CallCard
                  call={m}
                  transcript={transcriptFor(d, m._id)}
                  lookups={lookups}
                />
              ) : activity ? (
                <div
                  className={
                    "sales-chat-event " + (opportunity ? "opportunity" : "")
                  }
                >
                  {opportunity ? (
                    <GitBranch size={16} />
                  ) : (
                    <CircleDot size={16} />
                  )}
                  <span>
                    {events[text] || text || s("Событие GHL", "GHL event")}
                  </span>
                  <time>
                    {date
                      ? new Date(date).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : ""}
                  </time>
                </div>
              ) : (
                <article
                  className={
                    "sales-chat-bubble " +
                    (internal ? "note" : incoming ? "incoming" : "outgoing")
                  }
                >
                  <header>
                    {internal && <StickyNote size={15} />}
                    <strong>
                      {internal
                        ? s("Внутренняя заметка", "Internal note")
                        : incoming
                          ? clientName
                          : m.userId
                            ? userName(lookups, m.userId)
                            : s("Сообщение компании", "Company message")}
                    </strong>
                    <span>
                      {internal
                        ? m.userId
                          ? userName(lookups, m.userId)
                          : s("Автор не указан", "Author unavailable")
                        : m.messageType?.replace("TYPE_", "")}
                    </span>
                  </header>
                  <p>
                    {text ||
                      s(
                        "Сообщение без текстового содержимого",
                        "Message has no text content",
                      )}
                  </p>
                  <footer>
                    <time title={when(date)}>
                      {date
                        ? new Date(date).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </time>
                    {!internal && m.status && <span>{m.status}</span>}
                  </footer>
                </article>
              )}
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}
