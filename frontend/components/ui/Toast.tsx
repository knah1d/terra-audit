"use client";

import { CheckCircle2, Info, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useRef, useState } from "react";

type Tone = "success" | "danger" | "info";
type ToastEntry = { id: number; message: string; tone: Tone };

const TONE_ICON: Record<Tone, typeof CheckCircle2> = {
  success: CheckCircle2,
  danger: XCircle,
  info: Info,
};
const TONE_ACCENT: Record<Tone, string> = {
  success: "text-success-700",
  danger: "text-danger-700",
  info: "text-brand-700",
};

const ToastContext = createContext<{ show: (message: string, tone?: Tone) => void } | null>(null);

/** `useToast().show("Saved", "success")` — a small local primitive
 * (glass-chrome + this app's existing motion tokens) instead of a new
 * dependency like sonner, consistent with every other components/ui/
 * primitive built this session. Mount ToastProvider once near the root
 * so a toast fired right before a navigation (e.g. delete-then-redirect)
 * still has somewhere to render. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const nextId = useRef(0);

  const show = useCallback((message: string, tone: Tone = "success") => {
    const id = nextId.current++;
    setToasts((t) => [...t, { id, message, tone }]);
    setTimeout(() => {
      setToasts((t) => t.filter((entry) => entry.id !== id));
    }, 3200);
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div
        className="fixed bottom-5 right-5 flex flex-col gap-2"
        style={{ zIndex: "var(--z-index-sheet)" }}
      >
        {toasts.map((t) => {
          const Icon = TONE_ICON[t.tone];
          return (
            <div
              key={t.id}
              role="status"
              className="glass-chrome-strong toast-in flex items-center gap-2.5 rounded-xl px-4 py-3 text-sm text-text-primary"
            >
              <Icon className={`size-4 shrink-0 ${TONE_ACCENT[t.tone]}`} />
              {t.message}
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast() used outside a ToastProvider");
  return ctx;
}
