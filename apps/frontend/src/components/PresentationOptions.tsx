import { Calculator, Sigma } from "lucide-react";
import { useI18n } from "../lib/i18n";

export type PresentationVisibility = {
  show_grand_total: boolean;
  show_calculations: boolean;
};

export default function PresentationOptions({
  value,
  disabled,
  onChange,
}: {
  value: PresentationVisibility;
  disabled: boolean;
  onChange: (value: PresentationVisibility) => void;
}) {
  const { t } = useI18n();
  return (
    <div
      className="presentation-visibility"
      role="group"
      aria-label={t("Presentation visibility")}
    >
      {(
        [
          ["show_grand_total", "Show grand total in PDF", Sigma],
          ["show_calculations", "Show calculations in PDF", Calculator],
        ] as const
      ).map(([key, label, Icon]) => (
        <button
          type="button"
          key={key}
          disabled={disabled}
          aria-label={t(label)}
          title={t(label)}
          aria-pressed={value[key]}
          onClick={() => onChange({ ...value, [key]: !value[key] })}
        >
          <Icon size={17} aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}
