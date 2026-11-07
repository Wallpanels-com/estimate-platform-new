/** Presentation-only parsing. Source cells and saved links are never rewritten. */
export type StaffContactToken = {
  kind: "telegram" | "phone";
  value: string;
  start: number;
  end: number;
};
export function contactTokens(source: string): StaffContactToken[] {
  const tokens: StaffContactToken[] = [];
  for (const m of source.matchAll(/@[A-Za-z0-9_]{3,32}\b/g)) {
    if (m.index > 0 && /[\w.%+-]/.test(source[m.index - 1])) continue;
    tokens.push({
      kind: "telegram",
      value: m[0],
      start: m.index,
      end: m.index + m[0].length,
    });
  }
  for (const m of source.matchAll(/(?:\+?\d|\(\d)[\d \t().\-–]{4,}\d/g)) {
    const value = m[0].replace(/^(\d{7,15})\.0$/, "$1").trim();
    const digits = value.replace(/\D/g, "");
    if (
      digits.length < 7 ||
      digits.length > 15 ||
      /^\d{4}-\d{2}-\d{2}$/.test(value)
    )
      continue;
    if (tokens.some((t) => m.index < t.end && m.index + m[0].length > t.start))
      continue;
    tokens.push({
      kind: "phone",
      value,
      start: m.index,
      end: m.index + m[0].length,
    });
  }
  return tokens.sort((a, b) => a.start - b.start);
}
const trimSeparators = (text: string) =>
  text.replace(/^[\s:;,|/·\-–—]+|[\s:;,|/·\-–—]+$/g, "");
export function primaryContacts(source: string) {
  const tokens = contactTokens(source);
  let offset = 0;
  let remaining = "";
  for (const t of tokens) {
    remaining += source.slice(offset, t.start);
    offset = t.end;
  }
  remaining += source.slice(offset);
  return {
    telegram: [
      ...new Set(
        tokens.filter((t) => t.kind === "telegram").map((t) => t.value),
      ),
    ],
    phones: [
      ...new Set(tokens.filter((t) => t.kind === "phone").map((t) => t.value)),
    ],
    other: trimSeparators(remaining),
  };
}
export function emailContacts(source: string) {
  const email: string[] = [],
    paypal: string[] = [];
  let paypalNextLine = false;
  for (const line of source.split(/\r?\n/)) {
    const matches = [
      ...line.matchAll(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g),
    ];
    const markers = [
      ...line.matchAll(/\bpay[ \t-]*pal\b|\be-?mail[ \t]*:/gi),
    ].filter(
      (marker) =>
        !matches.some(
          (email) =>
            marker.index >= email.index &&
            marker.index < email.index + email[0].length,
        ),
    );
    matches.forEach((emailMatch, index) => {
      const previous = markers
        .filter((marker) => marker.index < emailMatch.index)
        .at(-1);
      const suffix = markers.find(
        (marker) =>
          /pay/i.test(marker[0]) &&
          marker.index > emailMatch.index + emailMatch[0].length &&
          !matches.some((next) => next.index > marker.index),
      );
      const isPayPal =
        suffix && index === matches.length - 1
          ? true
          : previous
            ? /pay/i.test(previous[0])
            : paypalNextLine;
      (isPayPal ? paypal : email).push(emailMatch[0]);
    });
    paypalNextLine =
      matches.length === 0 &&
      !!markers.length &&
      /pay/i.test(markers.at(-1)![0]);
  }
  const other = source
    .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, "")
    .replace(/pay[\s-]*pal/gi, "")
    .replace(/\b(?:e-?mail)\s*:?/gi, "")
    .split(/\r?\n/)
    .map(trimSeparators)
    .filter(Boolean)
    .join("\n");
  return { email: [...new Set(email)], paypal: [...new Set(paypal)], other };
}
export function locationName(source: string): string {
  const value = source.trim();
  const aliases: Record<string, string> = {
    ua: "Ukraine",
    ukr: "Ukraine",
    ukraine: "Ukraine",
    украина: "Ukraine",
    україна: "Ukraine",
    us: "USA",
    usa: "USA",
    "u.s.a.": "USA",
    "united states": "USA",
    "united states of america": "USA",
    america: "USA",
    америка: "USA",
    сша: "USA",
    europe: "Europe",
    европа: "Europe",
    європа: "Europe",
    another: "Other",
    other: "Other",
    pl: "Poland",
    poland: "Poland",
    tr: "Türkiye",
    turkey: "Türkiye",
    türkiye: "Türkiye",
  };
  if (aliases[value.toLowerCase()]) return aliases[value.toLowerCase()];
  // Keep cities and other source details when a known country code is used as a prefix.
  return value.replace(
    /^(UA|UKR|US|USA)(?=[, /])/i,
    (code) => aliases[code.toLowerCase()],
  );
}
export function documentLink(value?: string, link?: string): string | null {
  for (const candidate of [link, value]) {
    if (!candidate || /[\r\n]/.test(candidate)) continue;
    try {
      const url = new URL(candidate);
      if (url.protocol === "https:" || url.protocol === "http:")
        return candidate;
    } catch {
      /* Non-URL cell labels stay text. */
    }
  }
  return null;
}
export function documentCaption(value: string): string {
  return /^(?:link|ссылка|посилання|https?:\/\/\S+)$/i.test(value.trim())
    ? ""
    : value;
}
