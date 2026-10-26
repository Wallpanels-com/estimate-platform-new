import { useI18n } from "../lib/i18n";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";
import { Button } from "./ui";

interface Action {
  label: string;
  icon?: ReactNode;
  onSelect: () => void;
  disabled?: boolean;
  danger?: boolean;
}

/** Native popovers stay above scrolling rails and support light dismiss / Escape. */
export default function ActionMenu({
  label,
  actions,
  disabled = false,
}: {
  label: string;
  actions: Action[];
  disabled?: boolean;
}) {
  const { t } = useI18n();

  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const popover = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const menu = popover.current!;
    menu.setAttribute("popover", "auto");
    const update = () => setOpen(menu.matches(":popover-open"));
    menu.addEventListener("toggle", update);
    return () => menu.removeEventListener("toggle", update);
  }, []);
  useEffect(() => {
    if (!open) return;
    const dismiss = () => popover.current?.hidePopover();
    window.addEventListener("resize", dismiss);
    document.addEventListener("scroll", dismiss, {
      capture: true,
      passive: true,
    });
    return () => {
      window.removeEventListener("resize", dismiss);
      document.removeEventListener("scroll", dismiss, true);
    };
  }, [open]);
  return (
    <>
      <Button
        ref={trigger}
        variant="ghost"
        className="action-menu-trigger"
        aria-label={label}
        title={label}
        aria-expanded={open}
        aria-controls={id}
        disabled={disabled}
        onClick={() => {
          const menu = popover.current!;
          if (open) {
            menu.hidePopover();
            return;
          }
          const rect = trigger.current!.getBoundingClientRect();
          menu.showPopover();
          const size = menu.getBoundingClientRect();
          menu.style.left = `${Math.max(8, Math.min(rect.right - size.width, window.innerWidth - size.width - 8))}px`;
          menu.style.top = `${Math.max(8, rect.bottom + size.height + 6 < window.innerHeight ? rect.bottom + 6 : rect.top - size.height - 6)}px`;
        }}
      >
        <MoreHorizontal size={18} aria-hidden="true" />
      </Button>
      <div
        id={id}
        ref={popover}
        className="action-popover"
        role="group"
        aria-label={label}
      >
        {actions.map((action) => (
          <button
            type="button"
            key={action.label}
            disabled={action.disabled}
            className={action.danger ? "danger-action" : undefined}
            onClick={() => {
              popover.current?.hidePopover();
              trigger.current?.focus();
              action.onSelect();
            }}
          >
            <span aria-hidden="true">{action.icon}</span>
            {t(action.label)}
          </button>
        ))}
      </div>
    </>
  );
}
