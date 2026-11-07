import { useI18n } from "../lib/i18n";
import { FieldContext } from "../lib/fieldContext";
import {
  Children,
  cloneElement,
  isValidElement,
  createContext,
  forwardRef,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import { X, Check, AlertCircle, FolderOpen, Loader2 } from "lucide-react";
export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "primary" | "secondary" | "ghost" | "danger";
    busy?: boolean;
  }
>(function Button(
  { children, variant = "secondary", busy, className = "", ...props },
  ref,
) {
  return (
    <button
      type="button"
      ref={ref}
      {...props}
      disabled={props.disabled || busy}
      className={`button ${variant} ${className}`}
      aria-busy={busy || undefined}
    >
      {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : null}
      {children}
    </button>
  );
});
export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  const { t } = useI18n();

  const uid = useId();
  const controls = Children.toArray(children);
  const first = controls.find((child) => isValidElement(child));
  const id =
    isValidElement<{ id?: string }>(first) && first.props.id
      ? first.props.id
      : uid;
  const labelId = `${id}-label`;
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className={`field ${className}`}>
      <label htmlFor={id} id={labelId}>
        {t(label)}
      </label>
      <FieldContext.Provider value={{ id, labelId, hintId }}>
        {Children.map(children, (child) =>
          isValidElement<{ id?: string; "aria-describedby"?: string }>(child) &&
          ["input", "textarea", "select"].includes(String(child.type))
            ? cloneElement(child, {
                id: child.props.id || id,
                "aria-describedby":
                  [child.props["aria-describedby"], hintId]
                    .filter(Boolean)
                    .join(" ") || undefined,
              })
            : child,
        )}
      </FieldContext.Provider>
      {hint ? <small id={hintId}>{t(hint)}</small> : null}
    </div>
  );
}
const ModalExitContext = createContext(false);
export const MODAL_EXIT_MS = 150;

/** Keep a dismissed dialog mounted just long enough to finish its exit.
 * The parent still owns the open state and all save/dirty-close decisions.
 */
export function ModalPresence({ children }: { children: ReactNode }) {
  const parentClosing = useContext(ModalExitContext);
  const [previous, setPrevious] = useState(children);
  const [retained, setRetained] = useState(children);
  if (children !== previous) {
    setPrevious(children);
    if (children) setRetained(children);
  }
  const closing = !children && !!retained;
  useEffect(() => {
    if (!closing) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setRetained(null);
      return;
    }
    const timer = window.setTimeout(() => setRetained(null), MODAL_EXIT_MS);
    return () => window.clearTimeout(timer);
  }, [closing]);
  return (
    <ModalExitContext.Provider value={parentClosing || closing}>
      {children || retained}
    </ModalExitContext.Provider>
  );
}

export function Modal({
  title,
  children,
  onClose,
  wide = false,
  className = "",
  leading,
  description,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
  className?: string;
  leading?: ReactNode;
  description?: ReactNode;
}) {
  const { t } = useI18n();

  const closing = useContext(ModalExitContext);
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const d = ref.current!;
    const focus = document.activeElement as HTMLElement | null;
    if (!d.open) d.showModal();
    return () => {
      d.close();
      focus?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? "wide" : ""} ${className}`}
      aria-labelledby={titleId}
      data-closing={closing || undefined}
      onClickCapture={(event) => {
        if (closing) {
          event.preventDefault();
          event.stopPropagation();
        }
      }}
      onKeyDownCapture={(event) => {
        if (closing) {
          event.preventDefault();
          event.stopPropagation();
        }
      }}
      onSubmitCapture={(event) => {
        if (closing) {
          event.preventDefault();
          event.stopPropagation();
        }
      }}
      onCancel={(event) => {
        event.preventDefault();
        if (!closing) close.current();
      }}
      onClick={(e) => {
        if (!closing && e.target === e.currentTarget) {
          const r = e.currentTarget.getBoundingClientRect();
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            close.current();
        }
      }}
    >
      <header className="modal-header">
        {leading || description ? (
          <div className="modal-heading">
            {leading}
            <div className="modal-heading-text">
              <h2 id={titleId}>{t(title)}</h2>
              {description}
            </div>
          </div>
        ) : (
          <h2 id={titleId}>{t(title)}</h2>
        )}
        <Button
          variant="ghost"
          aria-label={t("Close dialog")}
          onClick={onClose}
          disabled={closing}
        >
          <X size={18} />
        </Button>
      </header>
      {children}
    </dialog>
  );
}
export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  const { t } = useI18n();

  return (
    <div className="empty-state">
      <FolderOpen size={30} aria-hidden="true" />
      <h2>{t(title)}</h2>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Loading({ label = "Loading…" }: { label?: string }) {
  const { t } = useI18n();

  return (
    <div className="loading" role="status">
      <Loader2 className="spin" size={20} />
      {t(label)}
    </div>
  );
}
export function ErrorNotice({
  children,
  retry,
}: {
  children: ReactNode;
  retry?: () => void;
}) {
  const { t } = useI18n();

  return (
    <div className="error-notice" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <span>{typeof children === "string" ? t(children) : children}</span>
      {retry ? <Button onClick={retry}>{t("Try again")}</Button> : null}
    </div>
  );
}
const NoticeContext = createContext<(text: string, error?: boolean) => void>(
  () => {},
);
export function NoticeProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();

  const [notice, setNotice] = useState<{ text: string; error: boolean } | null>(
    null,
  );
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const notify = useCallback((text: string, error = false) => {
    clearTimeout(timer.current);
    setNotice({ text, error });
    timer.current = setTimeout(() => setNotice(null), error ? 7000 : 3500);
  }, []);
  useEffect(() => () => clearTimeout(timer.current), []);
  return (
    <NoticeContext.Provider value={notify}>
      {children}
      <div className="notice-region" role="status" aria-live="polite">
        {notice ? (
          <div className={`toast ${notice.error ? "error" : ""}`}>
            {notice.error ? <AlertCircle size={18} /> : <Check size={18} />}
            <span>{t(notice.text)}</span>
            <button
              aria-label={t("Dismiss notification")}
              onClick={() => setNotice(null)}
            >
              <X size={16} />
            </button>
          </div>
        ) : null}
      </div>
    </NoticeContext.Provider>
  );
}
export const useNotice = () => useContext(NoticeContext);
export function Confirm({
  title,
  children,
  action,
  onConfirm,
  onClose,
  busy,
  variant = "danger",
  error,
}: {
  title: string;
  children: ReactNode;
  action: string;
  onConfirm: () => void;
  onClose: () => void;
  busy?: boolean;
  variant?: "primary" | "danger";
  error?: string;
}) {
  const { t } = useI18n();

  return (
    <Modal
      title={title}
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <div className="modal-body">
        <p>{children}</p>
        {error ? <ErrorNotice>{error}</ErrorNotice> : null}
      </div>
      <footer className="modal-footer">
        <Button onClick={onClose} disabled={busy} autoFocus>
          {t("Cancel")}
        </Button>
        <Button variant={variant} busy={busy} onClick={onConfirm}>
          {action}
        </Button>
      </footer>
    </Modal>
  );
}
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  const { t } = useI18n();

  return (
    <header className="page-header">
      <div className="min-zero">
        <h1>{t(title)}</h1>
        {description ? <p>{t(description)}</p> : null}
      </div>
      <div className="page-actions">{actions}</div>
    </header>
  );
}
