import { useI18n } from "../lib/i18n";
import { useEffect, useState } from "react";
import { Download, ExternalLink } from "lucide-react";
import { errorMessage } from "../lib/api";
import { estimatePdfLabel, type EstimatePdfMode } from "../lib/estimatePdf";
import PdfChecks, { type ExportChecks } from "./PdfChecks";
import { Button, ErrorNotice, Loading, Modal } from "./ui";

export default function EstimatePdfPreview({
  mode,
  filename,
  loadPdf,
  checks,
  onClose,
}: {
  mode: EstimatePdfMode;
  filename: string;
  loadPdf: () => Promise<Blob>;
  checks?: ExportChecks;
  onClose: () => void;
}) {
  const { t } = useI18n();

  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const label = t(estimatePdfLabel(mode));
  useEffect(() => {
    let disposed = false;
    let objectUrl = "";
    setUrl("");
    setError("");
    void (async () => {
      try {
        const blob = await loadPdf();
        if (disposed) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      } catch (err) {
        if (!disposed) setError(errorMessage(err));
      }
    })();
    return () => {
      disposed = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [loadPdf, attempt]);
  return (
    <Modal
      title={t("{0} preview", label)}
      onClose={onClose}
      wide
      className="proposal-preview"
    >
      <PdfChecks checks={checks} />
      <div className="proposal-preview-body">
        {error ? (
          <ErrorNotice retry={() => setAttempt((value) => value + 1)}>
            {error}
          </ErrorNotice>
        ) : url ? (
          <iframe src={`${url}#view=Fit`} title={t("{0} PDF", label)} />
        ) : (
          <Loading label={t("Preparing {0}…", label)} />
        )}
      </div>
      <footer className="modal-footer proposal-preview-footer">
        <p>
          {t("This preview keeps your saved estimate unchanged.")}{" "}
          {t("Presentations are always generated in English.")}
        </p>
        <div className="button-row">
          <Button onClick={onClose}>{t("Close")}</Button>
          {url ? (
            <>
              <a
                className="button secondary"
                href={url}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={16} aria-hidden="true" />
                {t("Open PDF")}
              </a>
              <a className="button primary" href={url} download={filename}>
                <Download size={16} aria-hidden="true" />
                {t("Download")} PDF
              </a>
            </>
          ) : null}
        </div>
      </footer>
    </Modal>
  );
}
