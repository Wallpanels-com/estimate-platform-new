/** Format a phone-only Telegram link; never infer a missing country code. */
export function telegramPhoneLink(phone: string): string | null {
  const value = phone.trim().replace(/^p:\s*/i, "");
  if (!/^[+\d\s().\-\u2010-\u2014]+$/.test(value)) return null;
  let number = value.replace(/[\s().\-\u2010-\u2014]/g, "");
  if (number.startsWith("00")) number = `+${number.slice(2)}`;
  // Bare short/local numbers are ambiguous; retain their text without a link.
  if (!number.startsWith("+")) {
    if (/^8\d{10}$/.test(number)) return null; // Ambiguous domestic trunk prefix.
    if (!/^[1-9]\d{10,14}$/.test(number)) return null;
    number = `+${number}`;
  }
  return /^\+[1-9]\d{6,14}$/.test(number) ? `https://t.me/${number}` : null;
}
