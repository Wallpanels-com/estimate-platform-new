/** Embed tokens live in memory and never overwrite a standalone browser session. */
export const isEmbedded =
  typeof window !== "undefined" && window.parent !== window;
export const portalOrigin = new URL(
  import.meta.env?.VITE_PORTAL_ORIGIN || "https://edu.wallpanels.com",
).origin;
let moduleValue = new URLSearchParams(
  typeof location === "undefined" ? "" : location.search,
).get("module");
try {
  if (isEmbedded && moduleValue)
    sessionStorage.setItem("wallpanels.embed.module", moduleValue);
  if (!moduleValue && isEmbedded)
    moduleValue = sessionStorage.getItem("wallpanels.embed.module");
} catch {
  /* module permissions are enforced by the server, independently of storage */
}
export const embeddedModule = moduleValue === "hr" ? "hr" : "estimating";
const memory = new Map<string, string>();
export const tokenStorage = isEmbedded
  ? {
      getItem: (key: string) => memory.get(key) ?? null,
      setItem: (key: string, value: string) => {
        memory.set(key, value);
      },
      removeItem: (key: string) => {
        memory.delete(key);
      },
    }
  : {
      getItem: (key: string) => localStorage.getItem(key),
      setItem: (key: string, value: string) => localStorage.setItem(key, value),
      removeItem: (key: string) => localStorage.removeItem(key),
    };
export function notifyPortal(message: object) {
  if (isEmbedded) window.parent.postMessage(message, portalOrigin);
}
