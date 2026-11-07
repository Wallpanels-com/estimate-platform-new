import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Paperclip, Download } from "lucide-react";
import { request, download, errorMessage } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { Button, ErrorNotice, useNotice } from "./ui";
type Attachment = { id: string; name: string; size: number };
export default function CandidateFiles({ id }: { id: string }) {
  const { t } = useI18n(),
    client = useQueryClient(),
    notice = useNotice(),
    input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const files = useQuery({
    queryKey: ["hr-files", id],
    queryFn: () => request<Attachment[]>(`/hr/candidates/${id}/files`),
  });
  async function upload(selected: FileList | null) {
    if (!selected?.length) return;
    setBusy(true);
    setError("");
    try {
      for (const file of Array.from(selected)) {
        if (file.size > 20 * 1024 * 1024)
          throw Error(t("Maximum file size is 20 MB."));
        const form = new FormData();
        form.append("file", file);
        await request(`/hr/candidates/${id}/files`, {
          method: "POST",
          body: form,
        });
      }
      notice(t("Files saved"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
      await client.invalidateQueries({ queryKey: ["hr-files", id] });
    }
  }
  return (
    <section className="hr-candidate-files">
      <div className="hr-section-heading">
        <h3>{t("Files")}</h3>
        <Button
          disabled={busy}
          busy={busy}
          onClick={() => input.current?.click()}
        >
          <Paperclip size={16} />
          {t("Add files")}
        </Button>
        <input
          hidden
          type="file"
          multiple
          ref={input}
          onChange={(e) => void upload(e.target.files)}
        />
      </div>
      {error && <ErrorNotice>{t(error)}</ErrorNotice>}
      {files.isError && (
        <ErrorNotice retry={() => void files.refetch()}>
          {t(errorMessage(files.error))}
        </ErrorNotice>
      )}
      <div className="hr-file-list">
        {files.data?.map((f) => (
          <div key={f.id}>
            <span>
              {f.name}
              <small>{Math.ceil(f.size / 1024)} KB</small>
            </span>
            <Button
              variant="ghost"
              aria-label={t("Download {0}", f.name)}
              onClick={() =>
                void download("/hr/candidate-files/" + f.id, f.name).catch(
                  (e) => setError(errorMessage(e)),
                )
              }
            >
              <Download size={17} />
            </Button>
          </div>
        ))}
      </div>
    </section>
  );
}
