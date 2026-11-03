import { Send } from "lucide-react";
import { telegramPhoneLink } from "../lib/contactLinks";
import { useI18n } from "../lib/i18n";

export default function CandidateTelegram({ phone }: { phone: string }) {
  const { t } = useI18n();
  const href = telegramPhoneLink(phone);
  if (!href) return null;
  return (
    <a
      className="hr-telegram"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      referrerPolicy="no-referrer"
      aria-label={t("Open Telegram by phone")}
    >
      <Send size={13} aria-hidden="true" />
      <span>Telegram</span>
    </a>
  );
}
