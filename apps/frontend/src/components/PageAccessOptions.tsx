import { PAGES, type PageKey } from "../lib/access";
import { useI18n } from "../lib/i18n";
export default function PageAccessOptions({
  pages,
  onChange,
  disabled = false,
}: {
  pages: PageKey[];
  onChange: (pages: PageKey[]) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  return (
    <fieldset className="access-options" disabled={disabled}>
      <legend className="sr-only">{t("Available pages")}</legend>
      {PAGES.map((page) => (
        <label className="access-option" key={page.key}>
          <input
            type="checkbox"
            checked={pages.includes(page.key)}
            onChange={(e) =>
              onChange(
                e.target.checked
                  ? [...pages, page.key]
                  : pages.filter((key) => key !== page.key),
              )
            }
          />
          <span>{t(page.label)}</span>
        </label>
      ))}
    </fieldset>
  );
}
