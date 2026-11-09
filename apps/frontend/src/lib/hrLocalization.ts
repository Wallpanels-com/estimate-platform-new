import { useQuery } from "@tanstack/react-query";
import { request, ApiError } from "./api";
import { useI18n } from "./i18n";
import { hrText } from "./hrText";

type Resource =
  | { scope: "vacancies" }
  | { scope: "candidate"; candidate_id: string }
  | { scope: "candidates"; candidate_ids: string[] };
const foreign =
  /[\p{Script=Cyrillic}\p{Script=Arabic}\p{Script=Han}\p{Script=Hebrew}\p{Script=Greek}]/u;

/** Translate saved display text only; source fields and draft edits stay intact. */
export function useHRLocalization(
  resource: Resource,
  values: string[],
  enabled = true,
) {
  const { language } = useI18n();
  const texts = [
    ...new Set(values.filter((v) => v && foreign.test(hrText(v, "en")))),
  ];
  const query = useQuery({
    queryKey: ["hr-localization", resource, texts],
    enabled: enabled && language === "en" && texts.length > 0,
    staleTime: Infinity,
    gcTime: 30 * 60_000,
    retry: (attempt, error) =>
      attempt < 28 &&
      error instanceof ApiError &&
      error.status === 409 &&
      error.message.includes("already being prepared"),
    retryDelay: 1000,
    refetchOnWindowFocus: false,
    queryFn: async ({ signal }) => {
      const translations: Record<string, string> = {};
      let batch: string[] = [],
        size = 0;
      async function send() {
        if (!batch.length) return;
        const result = await request<{ translations: Record<string, string> }>(
          "/hr/localize",
          {
            method: "POST",
            body: JSON.stringify({ ...resource, texts: batch }),
            signal,
          },
        );
        if (
          !result.translations ||
          batch.some(
            (text) =>
              typeof result.translations[text] !== "string" ||
              !result.translations[text].trim(),
          )
        ) {
          throw new ApiError(
            502,
            "Could not translate the HR content. Please try again.",
          );
        }
        Object.assign(translations, result.translations);
        batch = [];
        size = 0;
      }
      for (const text of texts) {
        if (batch.length >= 24 || size + text.length > 10_000) await send();
        batch.push(text);
        size += text.length;
      }
      await send();
      return translations;
    },
  });
  const display = (value: string) =>
    language === "en"
      ? (query.data?.[value] ?? hrText(value, language))
      : hrText(value, language);
  return {
    ...query,
    display,
    translating:
      enabled &&
      language === "en" &&
      texts.length > 0 &&
      !query.data &&
      !query.isError,
  };
}
