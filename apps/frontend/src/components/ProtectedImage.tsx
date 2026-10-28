import { useEffect, useState, type ImgHTMLAttributes } from "react";
import { useQuery } from "@tanstack/react-query";
import { API_ORIGIN, ApiError, TOKEN_KEY } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function ProtectedImage({
  imageId,
  ...props
}: ImgHTMLAttributes<HTMLImageElement> & { imageId: string }) {
  const { t } = useI18n();
  const [url, setUrl] = useState("");
  // Thumbnail and full-size viewer share one authenticated original. Keep it
  // briefly in memory only; sign-out clears the QueryClient and its blobs.
  const image = useQuery({
    queryKey: ["photo", imageId],
    staleTime: Infinity,
    gcTime: 15_000,
    queryFn: async ({ signal }) => {
      const response = await fetch(`${API_ORIGIN}/api/v1/media/${imageId}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) || ""}`,
        },
        signal,
      });
      if (!response.ok) {
        if (response.status === 401)
          window.dispatchEvent(new Event("wallpanels:unauthorized"));
        throw new ApiError(response.status, "Photo unavailable");
      }
      return response.blob();
    },
    retry: (attempt, error) =>
      !(error instanceof ApiError && error.status < 500) && attempt < 1,
  });
  useEffect(() => {
    if (!image.data) {
      setUrl("");
      return;
    }
    const objectUrl = URL.createObjectURL(image.data);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [image.data]);
  if (image.isError)
    return (
      <span className="photo-placeholder" role="status">
        {t("Photo unavailable")}
      </span>
    );
  if (!url)
    return (
      <span className="photo-placeholder" role="status">
        {t("Loading…")}
      </span>
    );
  return <img {...props} decoding="async" src={url} />;
}
