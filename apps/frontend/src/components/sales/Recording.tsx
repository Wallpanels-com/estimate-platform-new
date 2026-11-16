import { useEffect, useState } from "react";
import { API_ORIGIN, TOKEN_KEY, errorMessage } from "../../lib/api";
import { tokenStorage } from "../../lib/portal";
import { Button } from "../ui";
import { useSalesText } from "./shared";

export default function Recording({ id }: { id: string }) {
  const s = useSalesText();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );
  async function load() {
    setLoading(true);
    setError("");
    try {
      const r = await fetch(
        `${API_ORIGIN}/api/v1/sales/recordings/${encodeURIComponent(id)}`,
        {
          headers: {
            Authorization: `Bearer ${tokenStorage.getItem(TOKEN_KEY)}`,
          },
          signal: AbortSignal.timeout(30000),
        },
      );
      if (!r.ok)
        throw new Error(
          s("Запись недоступна через API", "Recording unavailable through API"),
        );
      setUrl(URL.createObjectURL(await r.blob()));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="sales-recording">
      {url ? (
        <audio controls src={url} />
      ) : (
        <Button variant="secondary" disabled={loading} onClick={load}>
          {loading
            ? s("Загрузка…", "Loading…")
            : s("Слушать запись", "Play recording")}
        </Button>
      )}
      {error && <small role="status">{error}</small>}
    </div>
  );
}
