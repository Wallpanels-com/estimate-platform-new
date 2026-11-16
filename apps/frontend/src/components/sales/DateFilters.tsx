import DatePicker, { dateKey } from "./DatePicker";
import { useSalesText } from "./shared";
export default function DateFilters({
  from,
  to,
  onChange,
  activity = false,
}: {
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
  activity?: boolean;
}) {
  const s = useSalesText();
  return (
    <div className="sales-date-filters">
      <div
        className="sales-date-presets"
        aria-label={s("Период", "Date range")}
      >
        <button
          type="button"
          aria-pressed={!from && !to}
          onClick={() => onChange("", "")}
        >
          {s("Всё время", "All dates")}
        </button>
        {[0, 1, 2].map((n) => {
          const d = new Date();
          d.setDate(d.getDate() - n);
          const key = dateKey(d);
          return (
            <button
              type="button"
              key={n}
              aria-pressed={from === key && to === key}
              onClick={() => onChange(key, key)}
            >
              {
                [
                  s("Сегодня", "Today"),
                  s("Вчера", "Yesterday"),
                  s("Позавчера", "Two days ago"),
                ][n]
              }
            </button>
          );
        })}
      </div>
      <DatePicker
        label={
          activity
            ? s("Последнее событие с", "Last event from")
            : s("Сделка создана с", "Opportunity created from")
        }
        value={from}
        onChange={(v) => onChange(v, to && v > to ? v : to)}
      />
      <DatePicker
        label={s("По включительно", "Through")}
        value={to}
        onChange={(v) => onChange(from && v && v < from ? v : from, v)}
      />
      <small>{Intl.DateTimeFormat().resolvedOptions().timeZone}</small>
    </div>
  );
}
