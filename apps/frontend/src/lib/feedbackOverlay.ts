import { useLayoutEffect, useState } from "react";

/** Keep feedback inside the active native modal's focus and top-layer boundary. */
export function useFeedbackOverlay() {
  const [container, setContainer] = useState<HTMLElement | null>(null);
  useLayoutEffect(() => {
    let stack: HTMLDialogElement[] = [];
    const update = () => {
      const open = Array.from(
        document.querySelectorAll<HTMLDialogElement>("dialog[open]"),
      );
      stack = stack.filter((dialog) => open.includes(dialog));
      for (const dialog of open)
        if (!stack.includes(dialog)) stack.push(dialog);
      const active = stack.at(-1) ?? null;
      setContainer((previous) => (previous === active ? previous : active));
    };
    update();
    const observer = new MutationObserver(update);
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["open"],
    });
    return () => observer.disconnect();
  }, []);
  return container;
}
