import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText, ChevronDown } from "lucide-react";
import { request, errorMessage } from "../../lib/api";
import type { GhlRecord } from "./types";
import { useSalesText, when } from "./shared";
export default function Transcript({
  id,
  initial,
}: {
  id: string;
  initial?: GhlRecord;
}) {
  const s = useSalesText();
  const [open, setOpen] = useState(false);
  const ready = !!initial?.segments?.length;
  const q = useQuery({
    queryKey: ["sales", "transcript", id],
    queryFn: () =>
      request<GhlRecord>(`/sales/transcripts/${encodeURIComponent(id)}`),
    enabled: open && !ready,
    refetchInterval: (query) =>
      [
        "queued",
        "processing",
        "rate_limited",
        "daily_limit",
        "unavailable",
      ].includes(query.state.data?.availability || "")
        ? 10000
        : false,
  });
  const data = ready ? initial : q.data || initial;
  const messages: Record<string, string> = {
    queued: s(
      "Расшифровка в очереди. Готовый текст появится здесь автоматически.",
      "Transcription queued. Text will appear here automatically.",
    ),
    processing: s("Распознаём аудиозапись…", "Transcribing recording…"),
    not_available: s(
      "Готового транскрипта в GHL нет. Проверяем аудиозапись для расшифровки.",
      "No GHL transcript. Checking the recording for transcription.",
    ),
    not_recorded: s(
      "GHL не предоставляет аудиозапись этого звонка. Без записи расшифровать его невозможно.",
      "GHL does not provide a recording for this call. A transcript cannot be created without audio.",
    ),
    daily_limit: s(
      "Достигнут дневной лимит расшифровки. Звонок остаётся в очереди.",
      "Daily transcription limit reached. The call remains queued.",
    ),
    rate_limited: s(
      "Groq временно ограничил обработку. Повторим автоматически.",
      "Groq temporarily limited processing. Retrying automatically.",
    ),
    too_large: s(
      "Запись превышает допустимый размер для расшифровки.",
      "Recording exceeds the transcription size limit.",
    ),
    no_speech: s(
      "Разборчивой речи в записи не найдено.",
      "No intelligible speech found in the recording.",
    ),
    unavailable: s(
      "Расшифровка сейчас недоступна. Повторная попытка запланирована.",
      "Transcription is temporarily unavailable. A retry is scheduled.",
    ),
  };
  return (
    <div className="sales-call-transcript">
      <button
        type="button"
        className="sales-transcript-toggle"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <FileText size={16} />
        {s("Транскрипт разговора", "Call transcript")}
        <ChevronDown size={15} />
        {ready && <span className="sales-badge">{s("Готов", "Ready")}</span>}
      </button>
      {open && (
        <div className="sales-transcript-content">
          {q.error ? (
            <p role="alert">{errorMessage(q.error)}</p>
          ) : data?.segments?.length ? (
            <>
              <small>
                {data.transcript_source === "groq"
                  ? s(
                      "Расшифровка Groq по аудио GHL. Возможны ошибки распознавания; говорящие не определены.",
                      "Groq transcription of GHL audio. Recognition may contain errors; speakers are not identified.",
                    )
                  : s(
                      "Транскрипт из GoHighLevel",
                      "Transcript from GoHighLevel",
                    )}
              </small>
              {data.segments.map((seg, i) => (
                <p key={i}>
                  <time>
                    {seg.startTime != null
                      ? `${Math.floor(seg.startTime / 60000)}:${String(Math.floor(seg.startTime / 1000) % 60).padStart(2, "0")}`
                      : ""}
                  </time>
                  <span>{seg.transcript || seg.text}</span>
                </p>
              ))}
            </>
          ) : (
            <p role="status">
              {messages[data?.availability || ""] ||
                s(
                  "Проверяем наличие транскрипта…",
                  "Checking transcript availability…",
                )}
              {data?.retry_at && (
                <>
                  {" "}
                  {s("Следующая попытка", "Next attempt")}:{" "}
                  {when(data.retry_at)}
                </>
              )}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
