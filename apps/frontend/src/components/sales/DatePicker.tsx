import { useEffect, useId, useRef, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, X } from "lucide-react";
import { useSalesText } from "./shared";

export function dateKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
const parse = (s: string) => {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
};
export default function DatePicker({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
}) {
  const s = useSalesText();
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(() => (value ? parse(value) : new Date()));
  const [focusDate, setFocusDate] = useState(value || dateKey(new Date()));
  function close() {
    panel.current?.hidePopover();
    setOpen(false);
  }
  function show() {
    const d = value ? parse(value) : new Date();
    setMonth(d);
    setFocusDate(dateKey(d));
    panel.current?.showPopover();
    setOpen(true);
  }
  useEffect(() => {
    panel.current?.setAttribute("popover", "manual");
  }, []);
  useEffect(() => {
    if (!open) return;
    const node = panel.current!;
    const rect = trigger.current!.getBoundingClientRect();
    node.style.left = `${Math.max(12, Math.min(rect.left, innerWidth - 308))}px`;
    node.style.top = `${Math.max(12, Math.min(rect.bottom + 8, innerHeight - 390))}px`;
    const outside = (e: Event) => {
      if (
        e.target instanceof Node &&
        !node.contains(e.target) &&
        !trigger.current?.contains(e.target)
      )
        close();
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        close();
        trigger.current?.focus();
      }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", key, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", key, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);
  useEffect(() => {
    if (open)
      panel.current
        ?.querySelector<HTMLButtonElement>(`[data-date="${focusDate}"]`)
        ?.focus();
  }, [open, focusDate, month]);
  function moveMonth(delta: number) {
    const next = new Date(month.getFullYear(), month.getMonth() + delta, 1);
    setMonth(next);
    setFocusDate(dateKey(next));
  }
  function choose(day: string) {
    onChange(day);
    close();
    trigger.current?.focus();
  }
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7;
  const days = Array.from(
    { length: 42 },
    (_, i) => new Date(first.getFullYear(), first.getMonth(), i - offset + 1),
  );
  return (
    <div className="sales-date-field">
      <span>{label}</span>
      <button
        type="button"
        className="choice-trigger sales-date-trigger"
        ref={trigger}
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        aria-haspopup="dialog"
        onClick={() => (open ? close() : show())}
      >
        <CalendarDays size={16} />
        <span>
          {value
            ? parse(value).toLocaleDateString(s("ru-RU", "en-US"))
            : s("Любая дата", "Any date")}
        </span>
      </button>
      <div
        ref={panel}
        id={id}
        role="dialog"
        aria-label={label}
        className="sales-calendar"
      >
        <div className="sales-calendar-heading">
          <button
            type="button"
            aria-label={s("Предыдущий месяц", "Previous month")}
            onClick={() => moveMonth(-1)}
          >
            <ChevronLeft size={18} />
          </button>
          <strong aria-live="polite">
            {month.toLocaleDateString(s("ru-RU", "en-US"), {
              month: "long",
              year: "numeric",
            })}
          </strong>
          <button
            type="button"
            aria-label={s("Следующий месяц", "Next month")}
            onClick={() => moveMonth(1)}
          >
            <ChevronRight size={18} />
          </button>
        </div>
        <div className="sales-calendar-week" aria-hidden="true">
          {s("Пн Вт Ср Чт Пт Сб Вс", "Mo Tu We Th Fr Sa Su")
            .split(" ")
            .map((x) => (
              <span key={x}>{x}</span>
            ))}
        </div>
        <div className="sales-calendar-days">
          {days.map((d) => {
            const key = dateKey(d);
            return (
              <button
                type="button"
                key={key}
                data-date={key}
                tabIndex={key === focusDate ? 0 : -1}
                aria-label={d.toLocaleDateString(s("ru-RU", "en-US"), {
                  dateStyle: "full",
                })}
                aria-pressed={value === key}
                aria-current={key === dateKey(new Date()) ? "date" : undefined}
                className={d.getMonth() !== month.getMonth() ? "outside" : ""}
                onClick={() => choose(key)}
                onKeyDown={(e) => {
                  const delta: Record<string, number> = {
                    ArrowLeft: -1,
                    ArrowRight: 1,
                    ArrowUp: -7,
                    ArrowDown: 7,
                  };
                  if (delta[e.key]) {
                    e.preventDefault();
                    const next = new Date(d);
                    next.setDate(next.getDate() + delta[e.key]);
                    setFocusDate(dateKey(next));
                    setMonth(next);
                  } else if (e.key === "PageUp" || e.key === "PageDown") {
                    e.preventDefault();
                    const next = new Date(
                      d.getFullYear(),
                      d.getMonth() + (e.key === "PageUp" ? -1 : 1),
                      1,
                    );
                    setMonth(next);
                    setFocusDate(dateKey(next));
                  }
                }}
              >
                {d.getDate()}
              </button>
            );
          })}
        </div>
        <div className="sales-calendar-actions">
          <button type="button" onClick={() => choose(dateKey(new Date()))}>
            {s("Сегодня", "Today")}
          </button>
          <button type="button" onClick={() => choose("")}>
            <X size={14} />
            {s("Сбросить", "Clear")}
          </button>
        </div>
      </div>
    </div>
  );
}
