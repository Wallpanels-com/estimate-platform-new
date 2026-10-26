import { API_ORIGIN, ApiError, TOKEN_KEY, safeFilename } from "./api";

export type EstimatePdfMode = "pre" | "final";
export interface EstimatePdfSource {
  id: string;
  mode: EstimatePdfMode;
  revision: string;
}

export function estimatePdfLabel(mode: EstimatePdfMode) {
  return mode === "pre" ? "Pre-Estimate" : "Final Estimate";
}

export function estimatePdfFilename(mode: EstimatePdfMode, clientName: string) {
  return `${estimatePdfLabel(mode)} - Wallpanels - ${safeFilename(clientName)}.pdf`;
}

export async function fetchEstimatePdf(
  source: EstimatePdfSource,
): Promise<Blob> {
  const endpoint = source.mode === "pre" ? "pre-estimate" : "final-estimate";
  const response = await fetch(
    `${API_ORIGIN}/api/v1/pdf/${source.id}/${endpoint}`,
    {
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) || ""}`,
      },
    },
  );
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("wallpanels:unauthorized"));
    let message = "The PDF could not be generated. Please try again.";
    try {
      const error = await response.json();
      if (typeof error.detail === "string") message = error.detail;
    } catch {
      // Keep a readable fallback if the server returned a non-JSON error.
    }
    throw new ApiError(response.status, message);
  }
  return response.blob();
}

// One snapshot per open Builder. Preview and both download controls share these
// exact bytes. A different estimate, mode or revision cannot reuse an old PDF.
export function createEstimatePdfLoader(fetchPdf = fetchEstimatePdf) {
  let current: { key: string; promise: Promise<Blob> } | null = null;
  return (source: EstimatePdfSource): Promise<Blob> => {
    const key = JSON.stringify([source.id, source.mode, source.revision]);
    if (current?.key === key) return current.promise;
    const promise = Promise.resolve().then(() => fetchPdf(source));
    current = { key, promise };
    void promise.catch(() => {
      if (current?.promise === promise) current = null;
    });
    return promise;
  };
}

export function downloadEstimatePdf(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}
