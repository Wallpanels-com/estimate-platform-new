import { useI18n } from "../lib/i18n";
import { useEffect, useRef, useState } from "react";
import { Mic, Square, Upload } from "lucide-react";
import { Modal, Button, Field, ErrorNotice } from "./ui";
import { request, post, errorMessage } from "../lib/api";
export default function AiInput({
  estimateId,
  zoneId,
  onApplied,
  onClose,
}: {
  estimateId: string;
  zoneId: string;
  onApplied: () => Promise<void>;
  onClose: () => void;
}) {
  const { t } = useI18n();

  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recording, setRecording] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const recorder = useRef<MediaRecorder>();
  const stream = useRef<MediaStream>();
  useEffect(
    () => () => {
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach((t) => t.stop());
    },
    [],
  );
  async function transcribe(file: File | Blob) {
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append(
      "file",
      file,
      file instanceof File ? file.name : "recording.webm",
    );
    try {
      const response = await request<{ transcript: string }>(
        `/voice/transcribe?estimate_id=${estimateId}`,
        { method: "POST", body: form },
      );
      setText(response.transcript);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  async function start() {
    setError("");
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      const rec = new MediaRecorder(stream.current);
      recorder.current = rec;
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = () => {
        stream.current?.getTracks().forEach((t) => t.stop());
        setRecording(false);
        transcribe(new Blob(chunks, { type: rec.mimeType }));
      };
      rec.start();
      setRecording(true);
    } catch {
      setError(
        "Microphone is unavailable. Allow microphone access or upload an audio file.",
      );
    }
  }
  async function analyze() {
    setBusy(true);
    setError("");
    try {
      await post("/voice/extract", {
        estimate_id: estimateId,
        zone_id: zoneId,
        text,
      });
      await onApplied();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
      setConfirm(false);
    }
  }
  return (
    <Modal title={t("Describe this zone")} onClose={onClose}>
      <div className="modal-body stack">
        <p>
          {t(
            "Enter a scope description or transcribe a voice note. AI analysis uses the configured OpenAI connection.",
          )}
        </p>
        {error ? <ErrorNotice>{error}</ErrorNotice> : null}
        <div className="button-row">
          <Button
            disabled={busy}
            onClick={recording ? () => recorder.current?.stop() : start}
          >
            {recording ? <Square size={16} /> : <Mic size={16} />}{" "}
            {recording ? t("Stop recording") : t("Record voice")}
          </Button>
          <label className="button secondary">
            <Upload size={16} />
            {t("Upload audio")}
            <input
              className="file-input"
              type="file"
              accept="audio/*,video/webm"
              disabled={busy || recording}
              onChange={(e) => {
                if (e.target.files?.[0]) transcribe(e.target.files[0]);
              }}
            />
          </label>
        </div>
        <Field label={t("Zone description")}>
          <textarea
            rows={7}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t("Describe the dimensions, materials, and scope…")}
          />
        </Field>
        {confirm ? (
          <div className="warning-notice">
            {t("Analysis replaces the current line items in this zone.")}{" "}
            <Button variant="danger" busy={busy} onClick={analyze}>
              {t("Replace items with AI result")}
            </Button>
          </div>
        ) : null}
      </div>
      <footer className="modal-footer">
        <Button onClick={onClose}>{t("Cancel")}</Button>
        <Button
          variant="primary"
          disabled={!text.trim() || recording}
          busy={busy}
          onClick={() => setConfirm(true)}
        >
          {t("Analyze description")}
        </Button>
      </footer>
    </Modal>
  );
}
