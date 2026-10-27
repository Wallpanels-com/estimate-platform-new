import type { Language } from "./locale";
import type { CategoryIcon } from "./category-icons";
export { categoryIcons } from "./category-icons";
export type { CategoryIcon } from "./category-icons";
export interface BookCategory {
  parent_id?: string | null;
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
  parent_id: entry.parent_id || null,
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

export function categoryTrail(entry: BookCategory, categories: BookCategory[]) {
  const trail: BookCategory[] = [];
  let current: BookCategory | undefined = entry;
  while (current && !trail.some((c) => c.id === current!.id)) {
    trail.unshift(current);
    current = categories.find((c) => c.id === current?.parent_id);
  }
  return trail;
}
export const categoryAvailable = (
  entry: BookCategory,
  categories: BookCategory[],
) => categoryTrail(entry, categories).every((c) => !c.archived);
export const categoryLabel = (
  entry: BookCategory,
  categories: BookCategory[],
  language: Language,
  t: (key: string) => string,
) =>
  categoryTrail(entry, categories)
    .map((c) => localized(c, language, t))
    .join(" / ");
export function orderedCategories(categories: BookCategory[]): BookCategory[] {
  const result: BookCategory[] = [];
  function visit(parent: string | null) {
    for (const c of categories.filter(
      (c) => (c.parent_id || null) === parent,
    )) {
      if (result.some((entry) => entry.id === c.id)) continue;
      result.push(c);
      visit(c.id);
    }
  }
  visit(null);
  return result;
}
