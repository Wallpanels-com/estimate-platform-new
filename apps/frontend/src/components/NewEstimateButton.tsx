import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown, ClipboardCheck, FileText, Plus } from "lucide-react";
import { useI18n } from "../lib/i18n";
import { Button } from "./ui";

export type NewEstimateType = "pre" | "final";

export default function NewEstimateButton({
  onSelect,
}: {
  onSelect: (type: NewEstimateType) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [focusAt, setFocusAt] = useState<number | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const options = useRef<(HTMLButtonElement | null)[]>([]);
  const pinned = useRef(false);
  const id = useId();
  function close() {
    setOpen(false);
    setFocusAt(null);
    pinned.current = false;
  }
  useEffect(() => {
    if (open && focusAt !== null) options.current[focusAt]?.focus();
  }, [open, focusAt]);
  useEffect(() => {
    if (!open) return;
    const dismiss = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) close();
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [open]);
  return (
    <div
      ref={root}
      className="new-estimate-menu"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => {
        if (!pinned.current) close();
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) close();
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape" && open) {
          event.preventDefault();
          event.stopPropagation();
          close();
          trigger.current?.focus();
        } else if (
          ["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)
        ) {
          event.preventDefault();
          pinned.current = true;
          const current = options.current.findIndex(
            (item) => item === document.activeElement,
          );
          const next =
            event.key === "Home"
              ? 0
              : event.key === "End"
                ? 1
                : current < 0
                  ? event.key === "ArrowUp"
                    ? 1
                    : 0
                  : (current + 1) % 2;
          setOpen(true);
          setFocusAt(next);
        }
      }}
    >
      <Button
        ref={trigger}
        variant="primary"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => {
          pinned.current = !pinned.current;
          setOpen(pinned.current);
          setFocusAt(null);
        }}
      >
        <Plus size={17} aria-hidden="true" />
        {t("New estimate")}
        <ChevronDown size={14} aria-hidden="true" />
      </Button>
      {open ? (
        <div
          id={id}
          className="new-estimate-options"
          role="menu"
          aria-label={t("New estimate")}
        >
          {(
            [
              ["pre", "Pre-Estimate", FileText],
              ["final", "Final Estimate", ClipboardCheck],
            ] as const
          ).map(([type, label, Icon], index) => (
            <button
              key={type}
              ref={(node) => {
                options.current[index] = node;
              }}
              type="button"
              role="menuitem"
              tabIndex={open ? 0 : -1}
              onClick={() => {
                close();
                trigger.current?.focus();
                onSelect(type);
              }}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{t(label)}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
