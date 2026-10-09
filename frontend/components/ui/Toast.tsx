"use client";

import { CheckCircle2, Info, XCircle, X } from "lucide-react";
import Link from "next/link";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { ApiError } from "@/lib/api";

type Tone = "success" | "danger" | "info";
type Action = { label: string; href?: string; onClick?: () => void };
export type ToastOptions = { title: string; description?: string; tone?: Tone; action?: Action };
type ToastEntry = ToastOptions & { id: number; tone: Tone };

const TONE_ICON: Record<Tone, typeof CheckCircle2> = { success: CheckCircle2, danger: XCircle, info: Info };
const TONE_ACCENT: Record<Tone, string> = { success: "text-success-700", danger: "text-danger-700", info: "text-brand-700" };
const TONE_BAR: Record<Tone, string> = { success: "bg-success-600", danger: "bg-danger-600", info: "bg-brand-600" };
// Success/info close themselves; errors stay until dismissed so they are read.
const AUTO_CLOSE_MS: Record<Tone, number | null> = { success: 4500, info: 4500, danger: null };
const MAX_VISIBLE = 3;

type ToastApi = {
  /** Legacy signature: show("Saved", "success"). */
  show: (message: string | ToastOptions, tone?: Tone) => void;
  success: (title: string, options?: Omit<ToastOptions, "title" | "tone">) => void;
  info: (title: string, options?: Omit<ToastOptions, "title" | "tone">) => void;
  /** Turns an API/JS error into a clear title + reason. */
  error: (error: unknown, title?: string, action?: Action) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

function describe(error: unknown): { title: string; description?: string } {
  if (error instanceof ApiError) {
    const title = error.status === 403 ? "Not allowed" : error.status === 404 ? "Not found"
      : error.status === 409 ? "Conflict" : error.status === 422 ? "Check the details"
      : error.status >= 500 ? "Server error — please try again" : "Request failed";
    return { title, description: error.detail };
  }
  if (error instanceof TypeError) return { title: "Network error", description: "Check your connection and try again." };
  return { title: "Something went wrong", description: error instanceof Error ? error.message : String(error ?? "") };
}

/** App-wide notifications: action results (saved / failed) always appear
 * here, bottom-right, never as text at the top of a page. Mount once near
 * the root so a toast fired just before navigation still renders. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const nextId = useRef(0);
  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((entry) => entry.id !== id)), []);

  const push = useCallback((options: ToastOptions) => {
    const id = nextId.current++;
    const tone = options.tone ?? "success";
    setToasts((t) => [{ ...options, tone, id }, ...t].slice(0, MAX_VISIBLE));
    const ms = AUTO_CLOSE_MS[tone];
    if (ms) setTimeout(() => dismiss(id), ms);
  }, [dismiss]);

  const api = useMemo<ToastApi>(() => ({
    show: (message, tone = "success") => push(typeof message === "string" ? { title: message, tone } : { tone, ...message }),
    success: (title, options) => push({ ...options, title, tone: "success" }),
    info: (title, options) => push({ ...options, title, tone: "info" }),
    error: (error, title, action) => {
      const described = describe(error);
      push({ tone: "danger", title: title ?? described.title, description: title ? described.description ?? described.title : described.description, action });
    },
  }), [push]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed bottom-5 left-5 right-5 flex flex-col gap-2 sm:left-auto sm:w-[26rem]" style={{ zIndex: "var(--z-index-sheet)" }}>
        {toasts.map((t) => {
          const Icon = TONE_ICON[t.tone];
          return (
            <div key={t.id} role={t.tone === "danger" ? "alert" : "status"} aria-live={t.tone === "danger" ? "assertive" : "polite"}
              className="glass-chrome-strong toast-in relative flex gap-3 overflow-hidden rounded-xl py-3 pl-4 pr-3 text-sm text-text-primary shadow-lg">
              <span aria-hidden className={`absolute inset-y-0 left-0 w-1 ${TONE_BAR[t.tone]}`} />
              <Icon className={`mt-0.5 size-5 shrink-0 ${TONE_ACCENT[t.tone]}`} />
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{t.title}</p>
                {t.description && <p className="mt-0.5 break-words text-text-secondary">{t.description}</p>}
                {t.action && (t.action.href ? (
                  <Link href={t.action.href} onClick={() => dismiss(t.id)} className={`mt-1.5 inline-block font-medium underline ${TONE_ACCENT[t.tone]}`}>{t.action.label}</Link>
                ) : (
                  <button type="button" onClick={() => { t.action?.onClick?.(); dismiss(t.id); }} className={`mt-1.5 font-medium underline ${TONE_ACCENT[t.tone]}`}>{t.action.label}</button>
                ))}
              </div>
              <button type="button" aria-label="Dismiss notification" onClick={() => dismiss(t.id)} className="self-start rounded-lg p-1 text-text-tertiary hover:text-text-primary"><X className="size-4" /></button>
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
