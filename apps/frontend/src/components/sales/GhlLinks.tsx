import {
  ExternalLink,
  ContactRound,
  MessagesSquare,
  BriefcaseBusiness,
} from "lucide-react";
import type { ContactDetail } from "./types";
import { useSalesText } from "./shared";
export function ghlLink(
  location: string,
  kind: "contact" | "conversation" | "opportunity",
  id: string,
) {
  const base = `https://app.gohighlevel.com/v2/location/${encodeURIComponent(location)}`;
  return `${base}/${kind === "contact" ? "contacts/detail" : kind === "conversation" ? "conversations/conversations" : "opportunities/list"}/${encodeURIComponent(id)}${kind === "opportunity" ? "?tab=OpportunityDetails" : ""}`;
}
export function GhlOpportunityLink({
  locationId,
  id,
}: {
  locationId: string;
  id: string;
}) {
  const s = useSalesText();
  return (
    <a
      className="sales-ghl-link"
      href={ghlLink(locationId, "opportunity", id)}
      target="_blank"
      rel="noopener noreferrer"
    >
      <BriefcaseBusiness size={15} />
      {s("Сделка в GHL", "Opportunity in GHL")}
      <ExternalLink size={13} />
    </a>
  );
}
export function GhlLinks({
  detail: d,
  contactId,
  onDeals,
}: {
  detail: ContactDetail;
  contactId: string;
  onDeals: () => void;
}) {
  const s = useSalesText();
  return (
    <nav
      className="sales-ghl-links"
      aria-label={s("Открыть в GoHighLevel", "Open in GoHighLevel")}
    >
      <a
        className="sales-ghl-link"
        href={ghlLink(d.location_id, "contact", contactId)}
        target="_blank"
        rel="noopener noreferrer"
      >
        <ContactRound size={15} />
        {s("Контакт в GHL", "Contact in GHL")}
        <ExternalLink size={13} />
      </a>
      {d.conversations[0] && (
        <a
          className="sales-ghl-link"
          href={ghlLink(d.location_id, "conversation", d.conversations[0]._id)}
          target="_blank"
          rel="noopener noreferrer"
        >
          <MessagesSquare size={15} />
          {s("Переписка в GHL", "Conversation in GHL")}
          <ExternalLink size={13} />
        </a>
      )}
      {d.opportunities.length === 1 ? (
        <GhlOpportunityLink
          locationId={d.location_id}
          id={d.opportunities[0]._id}
        />
      ) : d.opportunities.length > 1 ? (
        <button className="sales-ghl-link" onClick={onDeals}>
          <BriefcaseBusiness size={15} />
          {s("Выбрать сделку", "Choose opportunity")} ({d.opportunities.length})
        </button>
      ) : null}
    </nav>
  );
}
