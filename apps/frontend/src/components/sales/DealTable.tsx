import type { GhlRecord, Lookups } from "./types";
import { Blank, useSalesText, when, userName, stageName } from "./shared";
export default function DealTable({
  items,
  lookups,
  onContact,
  showComments = false,
}: {
  items: GhlRecord[];
  lookups?: Lookups;
  onContact: (id: string) => void;
  showComments?: boolean;
}) {
  const s = useSalesText();
  if (!items.length)
    return (
      <Blank>
        {s(
          "По выбранным фильтрам сделок нет",
          "No opportunities match these filters",
        )}
      </Blank>
    );
  return (
    <div className="sales-table-wrap">
      <table className="sales-table">
        <thead>
          <tr>
            {[
              s("Клиент / Opportunity", "Client / opportunity"),
              s("Воронка / этап", "Pipeline / stage"),
              s("Ответственный", "Owner"),
              s("Статус", "Status"),
              s("Сумма GHL", "GHL value"),
              s("Источник", "Source"),
              s("Обновлено", "Updated"),
              ...(showComments
                ? [s("Последняя заметка сейлза", "Latest internal note")]
                : []),
            ].map((x) => (
              <th key={x}>{x}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((o) => (
            <tr key={o._id}>
              <td>
                <button
                  className="sales-client-link"
                  disabled={!o.contactId}
                  onClick={() => o.contactId && onContact(o.contactId)}
                >
                  {o.contact?.name || o.name || o._id}
                </button>
                <small>{o.name}</small>
              </td>
              <td>
                {stageName(lookups, o.pipelineStageId)}
                <small>
                  {lookups?.pipelines.find((p) => p.id === o.pipelineId)
                    ?.name || "—"}
                </small>
              </td>
              <td>{userName(lookups, o.assignedTo)}</td>
              <td>
                <span
                  className={
                    "sales-badge " +
                    (o.status === "won"
                      ? "positive"
                      : o.status === "lost"
                        ? "concern"
                        : "")
                  }
                >
                  {o.status || "—"}
                </span>
              </td>
              <td className="sales-numeric">
                {o.monetaryValue == null
                  ? "—"
                  : Number(o.monetaryValue).toLocaleString()}
              </td>
              <td>{o.source || "—"}</td>
              <td>{when(o.updatedAt)}</td>
              {showComments && (
                <td className="sales-lead-comment">
                  {o._latest_comment ? (
                    <>
                      <p>
                        {(o._latest_comment.body || "").replace(
                          /<[^>]+>/g,
                          " ",
                        )}
                      </p>
                      <small>
                        {userName(lookups, o._latest_comment.userId)} ·{" "}
                        {when(o._latest_comment.dateAdded)}
                      </small>
                    </>
                  ) : (
                    <small>
                      {s(
                        "Откройте клиента для загрузки заметок",
                        "Open the client to load notes",
                      )}
                    </small>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
