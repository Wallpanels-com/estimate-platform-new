import { Phone, Users, Bot, UserRound } from "lucide-react";
import type { GhlRecord, Lookups } from "./types";
import { Blank, useSalesText, when, userName } from "./shared";
export default function Numbers({
  items,
  lookups,
}: {
  items: GhlRecord[];
  lookups?: Lookups;
}) {
  const s = useSalesText();
  if (!items.length)
    return (
      <Blank>
        {s(
          "Номера ещё не загружены. Проверьте состояние подключения.",
          "Numbers have not loaded. Check connection status.",
        )}
      </Blank>
    );
  return (
    <>
      <p className="sales-muted">
        {s(
          "Назначения обновляются примерно раз в минуту. Отсутствие персонального владельца не означает, что номер свободен: проверьте группу, ИИ и переадресацию. Все изменения выполняются в GHL.",
          "Assignments refresh approximately every minute. No direct owner does not mean a number is free: check groups, AI and forwarding. All changes are made in GHL.",
        )}
      </p>
      <div className="sales-number-grid">
        {items.map((n) => {
          const grouped = !!n.linkedRingAllUsers?.length;
          const routed = !!n.inboundCallService?.type;
          const noDirect = !n.linkedUser;
          const state = !n._active
            ? s("Больше не в активном списке GHL", "No longer listed as active")
            : n.linkedUser
              ? s("Назначен сотруднику", "Assigned to user")
              : grouped || routed || n.forwardingNumber
                ? s("Маршрутизация настроена", "Routing configured")
                : s(
                    "Назначения не указаны в API",
                    "No assignments reported by API",
                  );
          return (
            <article
              key={n._id}
              className={"sales-number " + (!n._active ? "inactive" : "")}
            >
              <div className="sales-row">
                <Phone size={19} />
                <span className="sales-badge">{state}</span>
              </div>
              <h2>{n.phoneNumber}</h2>
              <p>
                {n.friendlyName ||
                  (n.isDefaultNumber
                    ? s("Основной исходящий номер", "Default outbound number")
                    : "Wall Panels")}
              </p>
              <dl>
                <dt>
                  <UserRound size={15} />
                  {s("Сотрудник", "User")}
                </dt>
                <dd>
                  {noDirect
                    ? s("Не назначен персонально", "No direct assignment")
                    : userName(lookups, n.linkedUser)}
                </dd>
                <dt>
                  <Users size={15} />
                  {s("Группа звонков", "Ring group")}
                </dt>
                <dd>
                  {grouped
                    ? n
                        .linkedRingAllUsers!.map((id) => userName(lookups, id))
                        .join(", ")
                    : "—"}
                </dd>
                <dt>
                  <Bot size={15} />
                  {s("Входящие", "Inbound routing")}
                </dt>
                <dd>
                  {n.inboundCallService?.type || "—"}
                  {n.inboundCallService?.value &&
                    " · " +
                      (lookups?.agents.find(
                        (a) => a.id === n.inboundCallService?.value,
                      )?.name || n.inboundCallService.value)}
                </dd>
                {n.forwardingNumber && (
                  <>
                    <dt>{s("Переадресация", "Forwarding")}</dt>
                    <dd>{n.forwardingNumber}</dd>
                  </>
                )}
              </dl>
              <footer>
                <span>
                  {n.capabilities?.voice ? "Voice " : ""}
                  {n.capabilities?.sms ? "SMS" : ""}
                </span>
                <span>{when(n._synced_at)}</span>
              </footer>
            </article>
          );
        })}
      </div>
    </>
  );
}
