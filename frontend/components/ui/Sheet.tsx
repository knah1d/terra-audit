"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";

/** Native modal supplies focus containment, Escape handling, and focus restoration. */
export function Sheet({ open, onClose, title, children, placement = "center" }: {
  open: boolean;
  onClose: () => void;
  title?: string;
  placement?: "center" | "drawer";
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    const previousOverflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-label={title}
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          const bounds = event.currentTarget.getBoundingClientRect();
          if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) onClose();
        }
      }}
      className={`glass-chrome-strong sheet-panel fixed max-w-sm overflow-y-auto rounded-2xl p-6 text-text-primary backdrop:bg-black/40 ${placement === "drawer" ? "inset-y-3 left-auto right-3 m-0 h-[calc(100dvh-1.5rem)] max-h-none w-[min(320px,calc(100%_-_1.5rem))]" : "inset-0 m-auto max-h-[85dvh] w-[calc(100%_-_2rem)]"}`}
    >
      <button type="button" onClick={onClose} aria-label={title ? `Close ${title}` : "Close dialog"}
        className="absolute right-3 top-3 flex size-11 items-center justify-center rounded-lg text-text-secondary hover:bg-brand-50 hover:text-text-primary">
        <X className="size-5" aria-hidden />
      </button>
      {title && <h2 className="ui-section-title mb-4 pr-10">{title}</h2>}
      {children}
    </dialog>
  );
}
