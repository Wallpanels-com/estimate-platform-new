import { Fragment } from "react";
import {
  contactTokens,
  emailContacts,
  primaryContacts,
} from "../../lib/staffProfile";
import CopyContact from "../CopyContact";
import { Field } from "../ui";

export function StaffContacts({
  contact,
  email,
  ru,
}: {
  contact: string;
  email: string;
  ru: boolean;
}) {
  const contacts = primaryContacts(contact);
  const addresses = emailContacts(email);
  return (
    <>
      <ContactField
        label="Telegram"
        values={contacts.telegram}
        kind="telegram"
      />
      <ContactField
        label={ru ? "Телефон" : "Phone"}
        values={contacts.phones}
        kind="phone"
      />
      <ContactField
        label={ru ? "Электронная почта" : "Email"}
        values={addresses.email}
        kind="email"
      />
      <ContactField label="PayPal" values={addresses.paypal} kind="email" />
      {contacts.other && (
        <Field
          label={ru ? "Другой контакт" : "Other contact"}
          className="staff-profile-full"
        >
          <div className="staff-value">{contacts.other}</div>
        </Field>
      )}
      {addresses.other && (
        <Field
          label={ru ? "Дополнительные данные" : "Additional details"}
          className="staff-profile-full"
        >
          <div className="staff-value">{addresses.other}</div>
        </Field>
      )}
    </>
  );
}
function ContactField({
  label,
  values,
  kind,
}: {
  label: string;
  values: string[];
  kind: "telegram" | "phone" | "email";
}) {
  return (
    <Field label={label}>
      <div className="staff-contact-values">
        {values.length ? (
          values.map((v) => <CopyContact key={v} value={v} kind={kind} />)
        ) : (
          <span className="staff-value">—</span>
        )}
      </div>
    </Field>
  );
}

/** Keep relation/name text beside its original number; do not guess who owns a phone. */
export function StaffReserveContacts({ value }: { value: string }) {
  const tokens = contactTokens(value);
  let offset = 0;
  const content = tokens.map((token, i) => {
    const before = value.slice(offset, token.start);
    offset = token.end;
    return (
      <Fragment key={i}>
        {before}
        <CopyContact value={token.value} kind={token.kind} />
      </Fragment>
    );
  });
  return (
    <div className="staff-reserve-text">
      {content}
      {value.slice(offset) || (!value ? "—" : "")}
    </div>
  );
}
