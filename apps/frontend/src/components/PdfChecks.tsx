import { useI18n } from "../lib/i18n";

export type ExportChecks = {
  warnings: string[];
  errors: string[];
  missing_photo_zones?: string[];
};

export default function PdfChecks({ checks }: { checks?: ExportChecks }) {
  const { t } = useI18n();
  const issues = [...(checks?.errors || []), ...(checks?.warnings || [])];
  if (!issues.length) return null;
  return (
    <details className="export-check" open={!!checks?.errors.length}>
      <summary>
        {t("Review before export")} · {issues.length}
      </summary>
      <ul>
        {issues.map((issue) => (
          <li key={issue}>{t(issue)}</li>
        ))}
      </ul>
      {checks?.missing_photo_zones?.length ? (
        <p>
          {t(
            "Zones without a photo: {0}",
            checks.missing_photo_zones.join("; "),
          )}
        </p>
      ) : null}
    </details>
  );
}
