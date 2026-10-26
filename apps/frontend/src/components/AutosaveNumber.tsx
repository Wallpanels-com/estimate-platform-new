import { useEffect, useRef, useState, type InputHTMLAttributes } from "react";

/** Save after a short typing pause or immediately on blur; keep rejected input visible. */
export default function AutosaveNumber({
  initialValue,
  onSave,
  ...props
}: Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "defaultValue" | "onChange" | "onBlur"
> & {
  initialValue: string | number | null;
  onSave: (value: number | null) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState(String(initialValue ?? ""));
  const current = useRef(draft);
  const saved = useRef(initialValue == null ? null : Number(initialValue));
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const saving = useRef(false);
  const callback = useRef(onSave);
  callback.current = onSave;
  async function flush() {
    clearTimeout(timer.current);
    const value = current.current === "" ? null : Number(current.current);
    if (
      saving.current ||
      value === saved.current ||
      (value !== null && (!Number.isFinite(value) || value < 0))
    )
      return;
    saving.current = true;
    try {
      if (await callback.current(value)) saved.current = value;
    } finally {
      saving.current = false;
    }
  }
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      const next = current.current === "" ? null : Number(current.current);
      if (saving.current || next !== saved.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      clearTimeout(timer.current);
      window.removeEventListener("beforeunload", warn);
    };
  }, []);
  return (
    <input
      {...props}
      value={draft}
      onChange={(event) => {
        current.current = event.target.value;
        setDraft(event.target.value);
        clearTimeout(timer.current);
        timer.current = setTimeout(() => {
          void flush();
        }, 650);
      }}
      onBlur={() => {
        void flush();
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          void flush();
        }
      }}
    />
  );
}
