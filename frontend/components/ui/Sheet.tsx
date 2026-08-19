"use client";

import { useEffect, useRef } from "react";

/**
 * Centered glass sheet over a dimmed backdrop — the "clean sheets/modals"
 * primitive from the Liquid Glass brief. Generic on purpose (title +
 * children + footer slot) so any future confirm-style flow can use it;
 * this pass only retrofits DeleteFieldButton's inline confirm row with it.
 *
 * Dismiss via Escape or backdrop click; focus moves into the sheet on
 * open and the trigger regains focus on close (handled by the caller,
 * since only it knows which element opened the sheet).
 */
export function Sheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} aria-hidden />
      <div
        className="fixed inset-0 flex items-center justify-center p-4"
        style={{ zIndex: "var(--z-index-sheet)" }}
      >
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-label={title}
          tabIndex={-1}
          onClick={(e) => e.stopPropagation()}
          className="glass-chrome-strong sheet-panel w-full max-w-sm rounded-2xl p-6 outline-none"
        >
          {title && <h2 className="mb-3 text-lg font-semibold text-text-primary">{title}</h2>}
          {children}
        </div>
      </div>
    </>
  );
}
