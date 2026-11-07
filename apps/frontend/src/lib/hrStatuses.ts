import { useQuery } from "@tanstack/react-query";
import { request } from "./api";
export type HRStatus = {
  key: string;
  name_en: string;
  name_ru: string;
  version: number;
  count: number;
};
export const defaultStatuses: HRStatus[] = [
  ["new", "New candidate", "Новый кандидат"],
  ["review", "In review", "На рассмотрении"],
  ["contacted", "Contacted", "Связались"],
  ["interview", "Interview", "Собеседование"],
  ["offer", "Offer", "Предложение"],
  ["hired", "Hired", "Нанят"],
  ["rejected", "Not selected", "Не выбран"],
  ["archived", "Archived", "В архиве"],
].map(([key, name_en, name_ru]) => ({
  key,
  name_en,
  name_ru,
  version: 0,
  count: 0,
}));
export function useHRStatuses() {
  return useQuery({
    queryKey: ["hr-statuses"],
    queryFn: () => request<HRStatus[]>("/hr/statuses"),
    staleTime: 20000,
  });
}
export function statusLabel(
  statuses: HRStatus[],
  key: string,
  language: string,
) {
  const s = statuses.find((x) => x.key === key);
  return s ? (language === "ru" ? s.name_ru : s.name_en) : key;
}
