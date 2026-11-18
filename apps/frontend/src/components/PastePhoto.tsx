import type { ClipboardEvent } from "react";
import { useI18n } from "../lib/i18n";

/** Native paste is scoped to this field so text editors keep normal Ctrl/⌘+V. */
export default function PastePhoto({
  disabled,
  onFile,
  onError,
}: {
  disabled: boolean;
  onFile: (file: File) => void;
  onError: (message: string) => void;
}) {
  const { t } = useI18n();
  function paste(event: ClipboardEvent<HTMLTextAreaElement>) {
    event.preventDefault();
    if (disabled) return;
    const files = Array.from(event.clipboardData.files);
    if (files.length !== 1) {
      onError(
        files.length > 1
          ? "Paste one photo at a time."
          : "Copy the image itself or a screenshot, then paste it here.",
      );
      return;
    }
    onFile(files[0]);
  }
  return (
    <label className="photo-paste">
      <span>{t("Or paste an image")}</span>
      <textarea
        rows={2}
        value=""
        onChange={() => {}}
        onPaste={paste}
        disabled={disabled}
        aria-label={t("Paste zone photo")}
        placeholder={t("Click here and press Ctrl+V or ⌘V")}
        spellCheck={false}
      />
    </label>
  );
}
