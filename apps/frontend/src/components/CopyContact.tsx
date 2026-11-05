import { useI18n } from "../lib/i18n";
import { useNotice } from "./ui";
export default function CopyContact({
  value,
  kind,
  className = "",
}: {
  value: string;
  kind: "email" | "phone";
  className?: string;
}) {
  const { t } = useI18n();
  const notify = useNotice();
  if (!value) return null;
  return (
    <button
      type="button"
      className={`hr-contact hr-copy-contact ${className}`}
      aria-label={t(
        kind === "email" ? "Copy email {0}" : "Copy phone {0}",
        value,
      )}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          notify(t(kind === "email" ? "Email copied" : "Phone copied"));
        } catch {
          notify(
            t("Could not copy. Select and copy the contact manually."),
            true,
          );
        }
      }}
    >
      {value}
    </button>
  );
}
