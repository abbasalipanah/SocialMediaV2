import { type ReactNode, useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

type PopoverProps = {
  label: string;
  value?: string;
  className?: string;
  children: (close: () => void) => ReactNode;
};

export function Popover({ label, value, className = "", children }: PopoverProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const close = (restoreFocus = true) => {
    setOpen(false);
    if (restoreFocus) window.setTimeout(() => triggerRef.current?.focus(), 0);
  };

  useEffect(() => {
    if (!open) return;
    const handlePointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) close(false);
    };
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
      if (event.key === "Tab") {
        const focusable = Array.from(
          panelRef.current?.querySelectorAll<HTMLElement>(
            'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
          ) ?? [],
        );
        if (focusable.length === 0) {
          event.preventDefault();
          triggerRef.current?.focus();
          return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("pointerdown", handlePointer);
    document.addEventListener("keydown", handleKey);
    window.setTimeout(() => panelRef.current?.querySelector<HTMLElement>("button, input, a")?.focus(), 0);
    return () => {
      document.removeEventListener("pointerdown", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  return (
    <div className={`popover ${className}`} ref={rootRef}>
      <button
        aria-expanded={open}
        aria-haspopup="dialog"
        className="popover-trigger"
        onClick={() => setOpen((current) => !current)}
        ref={triggerRef}
        type="button"
      >
        <span className="popover-trigger-copy">
          <span className="popover-label">{label}</span>
          {value && <strong>{value}</strong>}
        </span>
        <ChevronDown aria-hidden="true" size={16} />
      </button>
      {open && (
        <div aria-label={label} aria-modal="false" className="popover-panel" ref={panelRef} role="dialog">
          {children(() => close())}
        </div>
      )}
    </div>
  );
}
