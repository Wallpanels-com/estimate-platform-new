export const PAGES = [
  { key: "estimates", label: "Estimates", path: "/" },
  { key: "quick_estimate", label: "Quick estimate", path: "/quick-estimate" },
  { key: "price_book", label: "Price book", path: "/price-book" },
  { key: "users", label: "Team accounts", path: "/users" },
  { key: "trash", label: "Trash", path: "/trash" },
] as const;
export type PageKey = (typeof PAGES)[number]["key"];
type Grants = {
  page_access?: readonly string[] | null;
  can_manage_access?: boolean;
};
export function canAccess(user: Grants | undefined, page: PageKey) {
  return (
    !!user &&
    (user.can_manage_access === true ||
      user.page_access == null ||
      user.page_access.includes(page))
  );
}
export function firstPage(user: Grants | undefined) {
  return PAGES.find((page) => canAccess(user, page.key))?.path || "/access";
}
