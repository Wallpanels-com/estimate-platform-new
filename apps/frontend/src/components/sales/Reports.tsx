import type { Lookups, Report } from "./types";
import { Blank, useSalesText, userName, stageName } from "./shared";
export default function Reports({
  report,
  lookups,
}: {
  report: Report;
  lookups?: Lookups;
}) {
  const s = useSalesText();
  return (
    <>
      <p className="sales-muted">
        {s(
          "Текущий срез GHL. Фильтр дат относится к созданию opportunity. Суммы — значения сделок из CRM, не оплаченная выручка. Историческая конверсия не восстанавливается из текущих этапов.",
          "Current GHL snapshot. Date filters use opportunity creation dates. Values are CRM deal amounts, not paid revenue. Historical conversion is not inferred from current stages.",
        )}
      </p>
      <div className="sales-metrics">
        <article>
          <span>{s("Сделок в выборке", "Filtered opportunities")}</span>
          <strong>{report.count.toLocaleString()}</strong>
        </article>
        {Object.entries(report.statuses).map(([k, v]) => (
          <article key={k}>
            <span>{k}</span>
            <strong>{v.toLocaleString()}</strong>
          </article>
        ))}
      </div>
      {!report.groups.length ? (
        <Blank>{s("Нет данных для отчёта", "No report data")}</Blank>
      ) : (
        <div className="sales-table-wrap">
          <table className="sales-table">
            <thead>
              <tr>
                {[
                  s("Воронка", "Pipeline"),
                  s("Этап", "Stage"),
                  s("Менеджер", "Manager"),
                  s("Статус", "Status"),
                  s("Сделок", "Deals"),
                  s("Сумма GHL", "GHL value"),
                ].map((x) => (
                  <th key={x}>{x}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {report.groups.map((g, i) => (
                <tr key={i}>
                  <td>
                    {lookups?.pipelines.find((p) => p.id === g.pipeline_id)
                      ?.name || g.pipeline_id}
                  </td>
                  <td>{stageName(lookups, g.stage_id)}</td>
                  <td>{userName(lookups, g.owner_id)}</td>
                  <td>{g.status}</td>
                  <td>{g.count}</td>
                  <td>{Number(g.value).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
