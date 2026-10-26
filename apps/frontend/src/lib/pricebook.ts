import type { Language } from "./locale";
import type { CategoryIcon } from "./category-icons";
export { categoryIcons } from "./category-icons";
export type { CategoryIcon } from "./category-icons";
export interface BookCategory {
  id: string;
  name: string;
  name_ru: string;
  description: string;
  description_ru: string;
  icon: CategoryIcon;
  archived: boolean;
  version: number;
  builtin: boolean;
  calculator_id: string | null;
}
export interface BookItem {
  id: string;
  category_id: string;
  name: string;
  name_ru: string;
  description: string;
  description_ru: string;
  kind: "work" | "material" | "service";
  unit: "SF" | "LF" | "ea" | "HR" | "Fixed";
  pricing_mode: "unit" | "fixed" | "unpriced";
  unit_price: string | null;
  default_quantity: string;
  parameters: { name: string; value: string }[];
  archived: boolean;
  version: number;
}
export interface BookData {
  categories: BookCategory[];
  items: BookItem[];
}
export const localized = (
  entry: { name: string; name_ru?: string },
  language: Language,
  t: (key: string) => string,
) => (language === "ru" ? entry.name_ru || t(entry.name) : entry.name);
export const categoryBody = (entry: BookCategory) => ({
  name: entry.name,
  name_ru: entry.name_ru,
  description: entry.description,
  description_ru: entry.description_ru,
  icon: entry.icon,
  archived: entry.archived,
  expected_version: entry.version,
});
export const itemBody = (entry: BookItem) => {
  const { id, version, ...data } = entry;
  return { ...data, expected_version: version };
};
export const itemKindLabel = {
  work: "Work item",
  material: "Material",
  service: "Service",
};
