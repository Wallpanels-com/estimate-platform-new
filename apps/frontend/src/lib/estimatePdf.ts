import { tokenStorage } from "./portal";
import { API_ORIGIN, ApiError, TOKEN_KEY, safeFilename } from "./api";

export type ProposalBrand = "wallpanels" | "verona";
export type EstimatePdfMode = "pre" | "final";
export interface EstimatePdfSource {
  id: string;
  mode: EstimatePdfMode;
  revision: string;
  brand?: ProposalBrand;
}

export function estimatePdfLabel(mode: EstimatePdfMode) {
  return mode === "pre" ? "Pre-Estimate" : "Final Estimate";
}

export function estimatePdfFilename(
  mode: EstimatePdfMode,
  clientName: string,
  brand: ProposalBrand = "wallpanels",
) {
  return `${estimatePdfLabel(mode)} - ${brand === "verona" ? "Verona Home" : "Wallpanels"} - ${safeFilename(clientName)}.pdf`;
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
        Authorization: `Bearer ${tokenStorage.getItem(TOKEN_KEY) || ""}`,
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

// Keep the last two snapshots in this open Builder only. Pre/Final can be
// revisited without another render; a different revision always needs fresh bytes.
export function createEstimatePdfLoader(fetchPdf = fetchEstimatePdf) {
  const snapshots = new Map<string, Promise<Blob>>();
  return (source: EstimatePdfSource): Promise<Blob> => {
    const key = JSON.stringify([
      source.id,
      source.mode,
      source.revision,
      source.brand || "wallpanels",
    ]);
    const cached = snapshots.get(key);
    if (cached) {
      snapshots.delete(key);
      snapshots.set(key, cached);
      return cached;
    }
    const promise = Promise.resolve().then(() => fetchPdf(source));
    snapshots.set(key, promise);
    while (snapshots.size > 2) snapshots.delete(snapshots.keys().next().value!);
    void promise.catch(() => {
      if (snapshots.get(key) === promise) snapshots.delete(key);
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
