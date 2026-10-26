import { useEffect, useState, type ImgHTMLAttributes } from "react";
import { API_ORIGIN, TOKEN_KEY } from "../lib/api";
import { useI18n } from "../lib/i18n";

export default function ProtectedImage({
  imageId,
  ...props
}: ImgHTMLAttributes<HTMLImageElement> & { imageId: string }) {
  const { t } = useI18n();
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const abort = new AbortController();
    let objectUrl = "";
    setUrl("");
    setFailed(false);
    void fetch(`${API_ORIGIN}/api/v1/media/${imageId}`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY) || ""}`,
      },
      signal: abort.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Photo unavailable");
        const blob = await response.blob();
        if (!abort.signal.aborted) {
          objectUrl = URL.createObjectURL(blob);
          setUrl(objectUrl);
        }
      })
      .catch(() => {
        if (!abort.signal.aborted) setFailed(true);
      });
    return () => {
      abort.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [imageId]);
  if (failed) return <span role="status">{t("Photo unavailable")}</span>;
  if (!url) return <span role="status">{t("Loading…")}</span>;
  return <img {...props} src={url} />;
}
