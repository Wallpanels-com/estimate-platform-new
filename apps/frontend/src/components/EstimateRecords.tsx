import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Archive } from "lucide-react";
import { request, post, download, errorMessage } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { Modal, Button, ErrorNotice, Loading } from "./ui";

type Entry = {
  id: string;
  actor_name: string;
  entity: string;
  action: string;
  created_at: string;
  changes: Record<
    string,
    { before: unknown; after: unknown; changed?: boolean }
  >;
};
type Saved = {
  id: string;
  version: number;
  kind: "pdf" | "xlsx";
  label: string;
  actor_name: string;
  created_at: string;
};
export default function EstimateRecords({
  id,
  onClose,
}: {
  id: string;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const client = useQueryClient();
  const [tab, setTab] = useState<"history" | "documents">("history");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const history = useQuery({
    queryKey: ["history", id],
    queryFn: () => request<Entry[]>(`/estimates/${id}/history`),
  });
  const documents = useQuery({
    queryKey: ["documents", id],
    queryFn: () => request<Saved[]>(`/estimates/${id}/documents`),
  });
  async function issue(kind: "xlsx") {
    setBusy(true);
    setError("");
    try {
      await post(`/estimates/${id}/documents`, {
        kind,
        label: "Issued document",
      });
      await client.invalidateQueries({ queryKey: ["documents", id] });
      await client.invalidateQueries({ queryKey: ["history", id] });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={t("History & saved documents")}
      onClose={() => {
        if (!busy) onClose();
      }}
      wide
    >
      <div className="modal-body records-body">
        <div className="segments">
          <button
            aria-pressed={tab === "history"}
            onClick={() => setTab("history")}
          >
            {t("Change history")}
          </button>
          <button
            aria-pressed={tab === "documents"}
            onClick={() => setTab("documents")}
          >
            {t("Saved documents")}
          </button>
        </div>
        {error ? <ErrorNotice>{error}</ErrorNotice> : null}
        {tab === "history" ? (
          <>
            <p className="form-hint">
              {t(
                "Changes are saved with the employee name. History starts when this feature is enabled.",
              )}
            </p>
            {history.isLoading ? (
              <Loading />
            ) : history.error ? (
              <ErrorNotice>{errorMessage(history.error)}</ErrorNotice>
            ) : history.data?.length ? (
              history.data.map((entry) => (
                <details className="record-row" key={entry.id}>
                  <summary>
                    <strong>{entry.actor_name}</strong> · {t(entry.action)} ·{" "}
                    {entry.entity}
                    <small>{new Date(entry.created_at).toLocaleString()}</small>
                  </summary>
                  <dl>
                    {Object.entries(entry.changes)
                      .filter(
                        ([key]) =>
                          !["branch_state", "pdf_layout"].includes(key),
                      )
                      .map(([key, change]) => (
                        <div key={key}>
                          <dt>{key}</dt>
                          <dd>
                            {change.changed
                              ? t("Changed")
                              : `${String(change.before ?? "—")} → ${String(change.after ?? "—")}`}
                          </dd>
                        </div>
                      ))}
                  </dl>
                </details>
              ))
            ) : (
              <p>{t("No changes recorded yet.")}</p>
            )}
          </>
        ) : (
          <>
            <p className="form-hint">
              {t(
                "PDF presentations are generated only for preview and download. Only XLSX versions can be saved here.",
              )}
            </p>
            <div className="record-actions">
              <Button busy={busy} onClick={() => issue("xlsx")}>
                <Archive size={16} />
                {t("Save XLSX version")}
              </Button>
            </div>
            {documents.isLoading ? (
              <Loading />
            ) : documents.error ? (
              <ErrorNotice>{errorMessage(documents.error)}</ErrorNotice>
            ) : (
              documents.data?.map((doc) => (
                <div className="record-row record-document" key={doc.id}>
                  <div>
                    <strong>
                      {doc.kind.toUpperCase()} · {t("Version")} {doc.version}
                    </strong>
                    <small>
                      {doc.actor_name} ·{" "}
                      {new Date(doc.created_at).toLocaleString()}
                    </small>
                  </div>
                  <Button
                    onClick={async () => {
                      try {
                        await download(
                          `/documents/${doc.id}?download=true`,
                          `Estimate-v${doc.version}.${doc.kind}`,
                        );
                      } catch (err) {
                        setError(errorMessage(err));
                      }
                    }}
                  >
                    <Download size={16} />
                    {t("Download")}
                  </Button>
                </div>
              ))
            )}
          </>
        )}
      </div>
      <footer className="modal-footer">
        <Button onClick={onClose} disabled={busy}>
          {t("Close")}
        </Button>
      </footer>
    </Modal>
  );
}
