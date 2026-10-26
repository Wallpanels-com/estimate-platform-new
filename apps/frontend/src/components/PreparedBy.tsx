import { UserRound } from "lucide-react";
import { useI18n } from "../lib/i18n";

export default function PreparedBy({
  name,
  className = "",
}: {
  name: string;
  className?: string;
}) {
  const { t } = useI18n();
  return (
    <div className={`field prepared-by ${className}`}>
      <span>{t("Prepared by")}</span>
      <div className="prepared-by-value">
        <UserRound size={17} aria-hidden="true" />
        <strong>{name}</strong>
      </div>
    </div>
  );
}
