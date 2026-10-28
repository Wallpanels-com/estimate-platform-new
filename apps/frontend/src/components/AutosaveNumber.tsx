import { useEffect, useRef, useState, type InputHTMLAttributes } from "react";

/** Save after a short typing pause or immediately on blur; keep rejected input visible. */
export default function AutosaveNumber({
  initialValue,
  onSave,
  onPendingChange,
  ...props
}: Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "defaultValue" | "onChange" | "onBlur"
> & {
  initialValue: string | number | null;
  onSave: (value: number | null) => Promise<boolean>;
  onPendingChange?: (pending: boolean) => void;
}) {
  const [draft, setDraft] = useState(String(initialValue ?? ""));
  const current = useRef(draft);
  const saved = useRef(initialValue == null ? null : Number(initialValue));
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const saving = useRef(false);
  const mounted = useRef(true);
  const focused = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  const pendingCallback = useRef(onPendingChange);
  pendingCallback.current = onPendingChange;
  const [failed, setFailed] = useState(false);
  const valueNow = () =>
    current.current === "" ? null : Number(current.current);
  const pending = () =>
    pendingCallback.current?.(saving.current || valueNow() !== saved.current);
  const callback = useRef(onSave);
  callback.current = onSave;
  async function flush() {
    clearTimeout(timer.current);
    const value = valueNow();
    if (
      saving.current ||
      value === saved.current ||
      (value !== null && (!Number.isFinite(value) || value < 0))
    )
      return;
    if (input.current && !input.current.validity.valid) {
      setFailed(true);
      return;
    }
    saving.current = true;
    pending();
    let success = false;
    try {
      success = await callback.current(value);
      if (success) saved.current = value;
    } catch {
      // Keep the draft. The owner reports the request error; never retry a
      // rejected write automatically, especially a colleague's revision conflict.
    } finally {
      saving.current = false;
      if (mounted.current) {
        setFailed(!success);
        pending();
        // A second input/blur while saving used to be dropped entirely.
        if (success && valueNow() !== saved.current) void flush();
      }
    }
  }
  useEffect(() => {
    const incoming = initialValue == null ? null : Number(initialValue);
    if (!saving.current && valueNow() === saved.current && !focused.current) {
      saved.current = incoming;
      current.current = String(initialValue ?? "");
      setDraft(current.current);
    }
  }, [initialValue]);
  useEffect(() => {
    mounted.current = true;
    const warn = (event: BeforeUnloadEvent) => {
      const next = current.current === "" ? null : Number(current.current);
      if (saving.current || next !== saved.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => {
      mounted.current = false;
      clearTimeout(timer.current);
      pendingCallback.current?.(false);
      window.removeEventListener("beforeunload", warn);
    };
  }, []);
  return (
    <input
      {...props}
      ref={input}
      value={draft}
      aria-invalid={failed || undefined}
      onFocus={() => {
        focused.current = true;
      }}
      onChange={(event) => {
        current.current = event.target.value;
        setDraft(event.target.value);
        setFailed(false);
        pending();
        clearTimeout(timer.current);
        timer.current = setTimeout(() => {
          void flush();
        }, 650);
      }}
      onBlur={() => {
        focused.current = false;
        if (!saving.current && valueNow() === saved.current) {
          saved.current = initialValue == null ? null : Number(initialValue);
          current.current = String(initialValue ?? "");
          setDraft(current.current);
        } else void flush();
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
