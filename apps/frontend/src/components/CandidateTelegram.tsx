import { Send } from "lucide-react";
import { telegramContactLink, telegramPhoneLink } from "../lib/contactLinks";
import { useI18n } from "../lib/i18n";

export default function CandidateTelegram({
  phone,
  username,
}: {
  phone: string;
  username?: string | null;
}) {
  const { t } = useI18n();
  const href = telegramContactLink(phone, username);
  if (!href) return null;
  const known = href.startsWith("https://");
  const web = known ? null : telegramPhoneLink(phone);
  return (
    <>
      <a
        className="hr-telegram"
        href={href}
        target={known ? "_blank" : undefined}
        rel="noopener noreferrer"
        referrerPolicy="no-referrer"
        aria-label={t(
          known ? "Open Telegram profile" : "Open Telegram by phone",
        )}
      >
        <Send size={13} aria-hidden="true" />
        <span>
          {known ? `@${username!.trim().replace(/^@/, "")}` : "Telegram"}
        </span>
      </a>
      {web && (
        <a
          className="hr-telegram-web"
          href={web}
          target="_blank"
          rel="noopener noreferrer"
          referrerPolicy="no-referrer"
          aria-label={t("Open Telegram in browser")}
        >
          {t("Web")}
        </a>
      )}
    </>
  );
}
