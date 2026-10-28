export const API_ORIGIN = (import.meta.env.VITE_API_ORIGIN || "").replace(
  /\/$/,
  "",
);
export const TOKEN_KEY = "wallpanels.token";
const revisions = new Map<string, string>();
function rememberRevision(value: unknown) {
  if (value && typeof value === "object") {
    const item = value as { id?: string; revision?: string };
    if (item.id && item.revision) revisions.set(item.id, item.revision);
  }
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const writing = !["GET", "HEAD"].includes(options.method || "GET");
  let estimateId = path.match(/^\/estimates\/([0-9a-f-]{36})(?:\/|$)/)?.[1];
  if (!estimateId && writing && typeof options.body === "string") {
    try {
      estimateId = JSON.parse(options.body).estimate_id;
    } catch {
      /* non-JSON body */
    }
  }
  if (writing && estimateId && !headers.has("If-Match")) {
    if (!revisions.has(estimateId)) await request(`/estimates/${estimateId}`);
    const revision = revisions.get(estimateId);
    if (revision) headers.set("If-Match", revision);
  }
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_ORIGIN}/api/v1${path}`, {
    ...options,
    headers,
    signal: options.signal
      ? AbortSignal.any([options.signal, AbortSignal.timeout(30_000)])
      : AbortSignal.timeout(30_000),
  });
  if (!response.ok) {
    let message = "The request could not be completed. Please try again.";
    try {
      const data = await response.json();
      message =
        typeof data.detail === "string"
          ? data.detail
          : Array.isArray(data.detail)
            ? data.detail.map((e: { msg: string }) => e.msg).join(". ")
            : message;
    } catch {
      /* Non-JSON server error. */
    }
    if (response.status === 401 && !path.startsWith("/auth/login"))
      window.dispatchEvent(new Event("wallpanels:unauthorized"));
    throw new ApiError(response.status, message);
  }
  const savedId = response.headers.get("X-Estimate-ID");
  const savedRevision = response.headers.get("X-Estimate-Revision");
  if (savedId && savedRevision) revisions.set(savedId, savedRevision);
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  rememberRevision(data);
  return data as T;
}
export const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
export const patch = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
export const remove = (path: string) =>
  request<void>(path, { method: "DELETE" });
export async function download(path: string, filename: string) {
  const response = await fetch(`${API_ORIGIN}/api/v1${path}`, {
    headers: {
      Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) || ""}`,
    },
  });
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("wallpanels:unauthorized"));
    throw new ApiError(
      response.status,
      "The export could not be downloaded. Please try again.",
    );
  }
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}
export function photoUrl(estimateId: string, zoneId: string, path: string) {
  return `${API_ORIGIN}/storage/images/${estimateId}/${zoneId}/${encodeURIComponent(path.split("/").pop() || "")}`;
}
const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});
export const money = (value: unknown) =>
  currencyFormatter.format(Number(value) || 0);
const dateFormatter = new Intl.DateTimeFormat("en-US", { dateStyle: "medium" });
export const dateLabel = (value: string) =>
  dateFormatter.format(new Date(value));
export const errorMessage = (error: unknown) =>
  error instanceof Error && error.name === "TimeoutError"
    ? "The request timed out. Review the saved data before trying again."
    : error instanceof TypeError &&
        /fetch|network|load failed/i.test(error.message)
      ? "Connection lost. Check your network and try again."
      : error instanceof Error
        ? error.message
        : "Something went wrong. Please try again.";
export const safeFilename = (value: string) =>
  value
    .replace(/[\\/:*?"<>|]/g, "")
    .trim()
    .slice(0, 120) || "Estimate";
