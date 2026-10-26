import russian from "./ru.json";

export type Language = "en" | "ru";
export const LANGUAGE_KEY = "wallpanels.ui-language";
const dictionary: Readonly<Record<string, string>> = russian;

export function readLanguage(): Language {
  try {
    return localStorage.getItem(LANGUAGE_KEY) === "ru" ? "ru" : "en";
  } catch {
    return "en";
  }
}

export function writeLanguage(language: Language) {
  try {
    localStorage.setItem(LANGUAGE_KEY, language);
  } catch {
    /* Language still works in memory when browser storage is unavailable. */
  }
}

export function translate(
  text: string,
  language: Language,
  ...values: unknown[]
) {
  const result = language === "ru" ? (dictionary[text] ?? text) : text;
  return result.replace(/\{(\d+)\}/g, (match, index: string) =>
    Number(index) < values.length ? String(values[Number(index)] ?? "") : match,
  );
}

export function countLabel(
  count: number,
  noun: "items" | "line items" | "estimates",
  language: Language,
) {
  if (language === "en")
    return `${count} ${count === 1 ? noun.slice(0, -1) : noun}`;
  const forms =
    noun === "estimates"
      ? ["смета", "сметы", "смет"]
      : ["позиция", "позиции", "позиций"];
  const rule = new Intl.PluralRules("ru").select(count);
  return `${count} ${forms[rule === "one" ? 0 : rule === "few" ? 1 : 2]}`;
}
