import { Settings2 } from "lucide-react";
import Select from "./Select";
import { Button } from "./ui";
import { useI18n } from "../lib/i18n";
import { defaultStatuses, useHRStatuses } from "../lib/hrStatuses";
export default function HRStatusSelect({
  id,
  value,
  onChange,
  onManage,
  all = false,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  onManage: () => void;
  all?: boolean;
}) {
  const { t, language } = useI18n();
  const { data = defaultStatuses } = useHRStatuses();
  return (
    <div className="hr-status-picker">
      <Select
        id={id}
        aria-label={t("Candidate status")}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {all && <option value="">{t("All active statuses")}</option>}
        {value && !data.some((s) => s.key === value) && (
          <option value={value}>{value}</option>
        )}
        {data.map((s) => (
          <option key={s.key} value={s.key}>
            {language === "ru" ? s.name_ru : s.name_en}
          </option>
        ))}
      </Select>
      <Button
        variant="ghost"
        aria-label={t("Manage statuses")}
        onClick={onManage}
      >
        <Settings2 size={17} />
      </Button>
    </div>
  );
}
