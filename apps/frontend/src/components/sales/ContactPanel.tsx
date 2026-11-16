import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { request, errorMessage } from "../../lib/api";
import { Modal, Button, ErrorNotice, Loading } from "../ui";
import type { ContactDetail, Lookups } from "./types";
import { useSalesText, when, userName, stageName, Blank } from "./shared";
import ReviewCard from "./ReviewCard";
import ChatTimeline, { CallsList } from "./ChatTimeline";
import { GhlLinks, GhlOpportunityLink } from "./GhlLinks";

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
    refetchInterval: 5000,
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
              <GhlLinks
                detail={d}
                contactId={id}
                onDeals={() => setTab("deals")}
              />
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
                <ChatTimeline detail={d} lookups={lookups} clientName={name} />
              )}
              {tab === "calls" && <CallsList detail={d} lookups={lookups} />}
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
                      <div className="sales-row">
                        <strong>{o.name}</strong>
                        <GhlOpportunityLink
                          locationId={d.location_id}
                          id={o._id}
                        />
                      </div>
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
