import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE = "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

export function Dialog({
  open,
  title,
  description,
  onClose,
  children,
  drawer = false,
}: {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  drawer?: boolean;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    const frame = window.requestAnimationFrame(() => {
      const target = panel.current?.querySelector<HTMLElement>(FOCUSABLE) ?? panel.current;
      target?.focus();
    });
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab" || !panel.current) return;
      const items = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.classList.add("dialog-open");
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("dialog-open");
      previousFocus.current?.focus();
    };
  }, [onClose, open]);

  if (!open) return null;
  return createPortal(
    <div className={`dialog-layer${drawer ? " drawer-layer" : ""}`}>
      <button aria-label="Close dialog" className="dialog-backdrop" onClick={onClose} type="button" />
      <div
        aria-describedby={description ? "dialog-description" : undefined}
        aria-labelledby="dialog-title"
        aria-modal="true"
        className={`dialog-panel${drawer ? " drawer-panel" : ""}`}
        ref={panel}
        role="dialog"
        tabIndex={-1}
      >
        <header className="dialog-header">
          <div><h2 id="dialog-title">{title}</h2>{description && <p id="dialog-description">{description}</p>}</div>
          <button aria-label="Close" className="dialog-close" onClick={onClose} type="button"><X size={20} /></button>
        </header>
        {children}
      </div>
    </div>,
    document.body,
  );
}
