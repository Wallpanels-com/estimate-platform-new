import { useI18n } from "../lib/i18n";
import type { ProposalBrand } from "../lib/estimatePdf";

export default function ProposalBrandSwitch({
  value,
  disabled,
  onChange,
}: {
  value: ProposalBrand;
  disabled: boolean;
  onChange: (brand: ProposalBrand) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="proposal-brand-row">
      <span>{t("Presentation brand")}</span>
      <div
        className="language-switch proposal-brand-switch"
        role="group"
        aria-label={t("Presentation brand")}
      >
        {(
          [
            ["wallpanels", "W", "WallPanels"],
            ["verona", "VH", "Verona Home"],
          ] as const
        ).map(([brand, short, label]) => (
          <button
            key={brand}
            type="button"
            aria-label={label}
            title={label}
            aria-pressed={value === brand}
            disabled={disabled}
            onClick={() => onChange(brand)}
          >
            {short}
          </button>
        ))}
      </div>
    </div>
  );
}
