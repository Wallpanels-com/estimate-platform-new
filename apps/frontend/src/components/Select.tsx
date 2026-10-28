import {
  Children,
  Fragment,
  isValidElement,
  useCallback,
  useContext,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type InputHTMLAttributes,
  type KeyboardEvent,
  type ReactElement,
  type ReactNode,
  type RefObject,
  type SelectHTMLAttributes,
} from "react";
import { Check, ChevronDown, Plus } from "lucide-react";
import { FieldContext } from "../lib/fieldContext";
import { useI18n } from "../lib/i18n";

export type Choice = {
  value: string;
  label: string;
  disabled?: boolean;
  keywords?: string;
  create?: boolean;
};
const text = (node: ReactNode): string =>
  Children.toArray(node)
    .map((child) =>
      isValidElement<{ children?: ReactNode }>(child)
        ? text(child.props.children)
        : String(child),
    )
    .join("");
function choices(children: ReactNode): Choice[] {
  return Children.toArray(children).flatMap((child) => {
    if (!isValidElement(child)) return [];
    const element = child as ReactElement<{
      value?: string | number;
      children?: ReactNode;
      disabled?: boolean;
    }>;
    if (element.type === Fragment) return choices(element.props.children);
    if (element.type !== "option") return [];
    const label = text(element.props.children);
    return [
      {
        value: String(element.props.value ?? label),
        label,
        disabled: element.props.disabled,
      },
    ];
  });
}

/** Shared listbox behavior for fixed choices and editable catalogue suggestions. */
export function useChoices(
  items: Choice[],
  selected: string,
  choose: (value: string) => void,
) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement | HTMLInputElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const search = useRef({ text: "", time: 0 });
  const close = useCallback(() => {
    menu.current?.hidePopover();
    setOpen(false);
  }, []);
  const position = useCallback(() => {
    const node = menu.current;
    const rect = trigger.current?.getBoundingClientRect();
    if (!node || !rect) return;
    const below = window.innerHeight - rect.bottom - 14;
    const above = rect.top - 14;
    const upwards = below < 200 && above > below;
    const width = Math.min(Math.max(rect.width, 200), window.innerWidth - 24);
    node.style.width = `${width}px`;
    node.style.maxHeight = `${Math.min(300, Math.max(80, upwards ? above : below))}px`;
    node.style.left = `${Math.max(12, Math.min(rect.left, window.innerWidth - width - 12))}px`;
    node.style.top = `${upwards ? Math.max(12, rect.top - node.getBoundingClientRect().height - 6) : rect.bottom + 6}px`;
  }, []);
  useEffect(() => {
    const node = menu.current!;
    // Native auto light-dismiss can close a list opened by input focus during
    // the same pointer click. Keep the top layer, but own dismissal explicitly.
    node.setAttribute("popover", "manual");
    const toggle = () => setOpen(node.matches(":popover-open"));
    node.addEventListener("toggle", toggle);
    return () => node.removeEventListener("toggle", toggle);
  }, []);
  useEffect(() => {
    if (!open) return;
    const outside = (event: Event) => {
      if (!(event.target instanceof Node)) return;
      if (
        menu.current?.contains(event.target) ||
        trigger.current?.closest(".choice")?.contains(event.target)
      )
        return;
      close();
    };
    const dismiss = (event: Event) => {
      if (
        event.type === "scroll" &&
        event.target instanceof Node &&
        menu.current?.contains(event.target)
      )
        return;
      const rect = trigger.current?.getBoundingClientRect();
      if (rect && (rect.bottom < 0 || rect.top > window.innerHeight)) close();
      else position();
    };
    window.addEventListener("resize", dismiss);
    document.addEventListener("scroll", dismiss, true);
    document.addEventListener("pointerdown", outside, true);
    document.addEventListener("focusin", outside);
    return () => {
      window.removeEventListener("resize", dismiss);
      document.removeEventListener("scroll", dismiss, true);
      document.removeEventListener("pointerdown", outside, true);
      document.removeEventListener("focusin", outside);
    };
  }, [open, close, position]);
  useEffect(() => {
    const list = menu.current;
    const option = list?.querySelector('[data-active="true"]');
    if (!open || !list || !option) return;
    const itemRect = option.getBoundingClientRect();
    const listRect = list.getBoundingClientRect();
    if (itemRect.bottom > listRect.bottom - 6)
      list.scrollTop += itemRect.bottom - listRect.bottom + 6;
    else if (itemRect.top < listRect.top + 6)
      list.scrollTop -= listRect.top + 6 - itemRect.top;
  }, [active, open, items[active]?.value]);
  function show(
    index = items.findIndex(
      (item) => item.value === selected && !item.disabled,
    ),
  ) {
    menu.current!.showPopover();
    position();
    setActive(index >= 0 ? index : items.findIndex((item) => !item.disabled));
    setOpen(true);
  }
  function select(value: string) {
    choose(value);
    close();
    trigger.current?.focus();
  }
  function onKeyDown(event: KeyboardEvent, editable = false) {
    if (event.key === "Escape" && open) {
      event.preventDefault();
      event.stopPropagation();
      close();
      return;
    }
    if (event.key === "Tab") {
      close();
      return;
    }
    const available = items
      .map((item, index) => (item.disabled ? -1 : index))
      .filter((index) => index >= 0);
    if (["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      if (!open) show();
      else {
        const pos = available.indexOf(active);
        setActive(
          available[
            (pos + (event.key === "ArrowDown" ? 1 : -1) + available.length) %
              available.length
          ] ?? -1,
        );
      }
    } else if (open && ["Home", "End"].includes(event.key)) {
      event.preventDefault();
      setActive(
        event.key === "Home" ? (available[0] ?? -1) : (available.at(-1) ?? -1),
      );
    } else if (event.key === "Enter" || (!editable && event.key === " ")) {
      event.preventDefault();
      if (open && items[active] && !items[active].disabled)
        select(items[active].value);
      else if (open) close();
      else show();
    } else if (
      !editable &&
      event.key.length === 1 &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.altKey
    ) {
      event.preventDefault();
      const now = Date.now();
      search.current = {
        text:
          (now - search.current.time < 700 ? search.current.text : "") +
          event.key.toLocaleLowerCase(),
        time: now,
      };
      const match = items.findIndex(
        (item) =>
          !item.disabled &&
          item.label.toLocaleLowerCase().startsWith(search.current.text),
      );
      if (match >= 0) {
        if (!open) show(match);
        else setActive(match);
      }
    }
  }
  return {
    id,
    trigger,
    menu,
    open,
    active,
    setActive,
    close,
    show,
    select,
    onKeyDown,
  };
}
export function ChoiceMenu({
  controller: c,
  items,
  selected,
  label,
  labelId,
}: {
  controller: ReturnType<typeof useChoices>;
  items: Choice[];
  selected: string;
  label?: string;
  labelId?: string;
}) {
  const { t } = useI18n();
  return (
    <div
      id={c.id}
      ref={c.menu}
      className="choice-menu"
      role="listbox"
      aria-label={label}
      aria-labelledby={labelId}
    >
      {items.length ? (
        items.map((item, index) => (
          <div
            key={item.value}
            id={`${c.id}-${index}`}
            role="option"
            aria-selected={item.value === selected}
            aria-disabled={item.disabled || undefined}
            className={item.create ? "choice-create" : undefined}
            data-active={index === c.active}
            onMouseDown={(event) => event.preventDefault()}
            onMouseMove={() => !item.disabled && c.setActive(index)}
            onClick={() => !item.disabled && c.select(item.value)}
          >
            <span>
              {item.create ? <Plus size={15} aria-hidden="true" /> : null}
              {item.label}
            </span>
            {item.value === selected ? (
              <Check size={15} aria-hidden="true" />
            ) : null}
          </div>
        ))
      ) : (
        <p>{t("No matching options. You can enter your own value.")}</p>
      )}
    </div>
  );
}

/** A styled listbox backed by a native select for unchanged FormData/change events. */
export default function Select({
  children,
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  const field = useContext(FieldContext);
  const uid = useId();
  const native = useRef<HTMLSelectElement>(null);
  const items = choices(children);
  const [current, setCurrent] = useState(
    String(props.value ?? props.defaultValue ?? items[0]?.value ?? ""),
  );
  const selected = String(props.value ?? current);
  const c = useChoices(items, selected, (value) => {
    const node = native.current!;
    node.value = value;
    node.dispatchEvent(new Event("change", { bubbles: true }));
  });
  useLayoutEffect(() => {
    setCurrent(native.current!.value);
  });
  useEffect(() => {
    const form = native.current?.form;
    const reset = () =>
      queueMicrotask(() => setCurrent(native.current?.value ?? ""));
    form?.addEventListener("reset", reset);
    return () => form?.removeEventListener("reset", reset);
  }, []);
  const labelId =
    props["aria-labelledby"] ||
    (!props["aria-label"] ? field?.labelId : undefined);
  return (
    <div className={`choice ${className}`}>
      <button
        ref={c.trigger as RefObject<HTMLButtonElement>}
        id={props.id || field?.id || uid}
        type="button"
        className="choice-trigger"
        role="combobox"
        disabled={props.disabled}
        aria-label={props["aria-label"]}
        aria-labelledby={labelId}
        aria-describedby={props["aria-describedby"] || field?.hintId}
        aria-expanded={c.open}
        aria-controls={c.id}
        aria-haspopup="listbox"
        aria-required={props.required || undefined}
        aria-invalid={props["aria-invalid"]}
        aria-activedescendant={
          c.open && c.active >= 0 ? `${c.id}-${c.active}` : undefined
        }
        onKeyDown={(event) => c.onKeyDown(event)}
        onClick={() => (c.open ? c.close() : c.show())}
      >
        <span>
          {items.find((item) => item.value === selected)?.label || "—"}
        </span>
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      <select
        {...props}
        id={undefined}
        className="choice-native"
        hidden
        ref={native}
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          setCurrent(event.currentTarget.value);
          props.onChange?.(event);
        }}
        onInvalid={(event) => {
          event.preventDefault();
          c.trigger.current?.focus();
          props.onInvalid?.(event);
        }}
      >
        {children}
      </select>
      <ChoiceMenu
        controller={c}
        items={items}
        selected={selected}
        label={props["aria-label"]}
        labelId={labelId}
      />
    </div>
  );
}

/** Editable suggestions retain free entry and original catalogue values in the form. */
export function Combobox({
  options,
  onValueChange,
  defaultValue = "",
  ...props
}: Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "onChange" | "value" | "defaultValue" | "list"
> & {
  options: Choice[];
  onValueChange?: (value: string) => void;
  defaultValue?: string;
}) {
  const field = useContext(FieldContext);
  const uid = useId();
  const [value, setValue] = useState(defaultValue);
  const [query, setQuery] = useState("");
  const items = options.filter((item) =>
    `${item.label} ${item.value}`
      .toLocaleLowerCase()
      .includes(query.toLocaleLowerCase()),
  );
  const c = useChoices(items, value, (chosen) => {
    setValue(chosen);
    setQuery("");
    onValueChange?.(chosen);
  });
  return (
    <div className="choice editable-choice">
      <input
        {...props}
        ref={c.trigger as RefObject<HTMLInputElement>}
        id={props.id || field?.id || uid}
        value={value}
        role="combobox"
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={c.open}
        aria-controls={c.id}
        aria-labelledby={
          props["aria-labelledby"] ||
          (!props["aria-label"] ? field?.labelId : undefined)
        }
        aria-describedby={props["aria-describedby"] || field?.hintId}
        aria-activedescendant={
          c.open && c.active >= 0 && items[c.active]
            ? `${c.id}-${c.active}`
            : undefined
        }
        onKeyDown={(event) => c.onKeyDown(event, true)}
        onChange={(event) => {
          setValue(event.target.value);
          setQuery(event.target.value);
          onValueChange?.(event.target.value);
          c.setActive(0);
          if (!c.open) c.show(0);
        }}
        onClick={() => {
          setQuery("");
          if (!c.open) c.show();
        }}
      />
      <button
        type="button"
        className="choice-toggle"
        tabIndex={-1}
        aria-labelledby={field?.labelId}
        aria-label={props["aria-label"]}
        disabled={props.disabled}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => {
          setQuery("");
          c.trigger.current?.focus();
          c.open ? c.close() : c.show();
        }}
      >
        <ChevronDown size={16} aria-hidden="true" />
      </button>
      <ChoiceMenu
        controller={c}
        items={items}
        selected={value}
        label={props["aria-label"]}
        labelId={field?.labelId}
      />
    </div>
  );
}
