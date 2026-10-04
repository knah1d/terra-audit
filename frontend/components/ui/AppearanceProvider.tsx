"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { apiFetch } from "@/lib/api";

type Preference = "system" | "light" | "dark";
type Preferences = { theme_preference: Preference };
type Appearance = {
  select: (value: Preference) => void;
  retry: () => void;
  error: string | null;
  saving: boolean;
};
const Context = createContext<Appearance | null>(null);

export function useAppearance() {
  const value = useContext(Context);
  if (!value) throw new Error("AppearanceProvider missing");
  return value;
}

export function AppearanceProvider({ authenticated, children }: {
  authenticated: boolean; children: React.ReactNode;
}) {
  const { setTheme } = useTheme();
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const revision = useRef(0);
  const latest = useRef<Preference | null>(null);
  const pending = useRef<Preference | null>(null);
  const busy = useRef(false);
  const lifecycle = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    lifecycle.current = controller;
    const initialRevision = revision.current;
    if (authenticated) {
      void apiFetch<Preferences>("/auth/me/preferences", { signal: controller.signal })
        .then((result) => {
          if (!controller.signal.aborted && revision.current === initialRevision) {
            setTheme(result.theme_preference);
          }
        }).catch(() => {
          if (!controller.signal.aborted && revision.current === initialRevision) {
            setError("Couldn’t load your account appearance. Select a mode to save it.");
          }
        });
    }
    return () => controller.abort();
  }, [authenticated, setTheme]);

  async function drain() {
    const controller = lifecycle.current;
    if (busy.current || !controller || controller.signal.aborted) return;
    busy.current = true;
    setSaving(true);
    try {
      while (pending.current && !controller.signal.aborted) {
        const value = pending.current;
        pending.current = null;
        try {
          await apiFetch<Preferences>("/auth/me/preferences", {
            method: "PUT", json: { theme_preference: value }, signal: controller.signal,
          });
          if (!controller.signal.aborted && latest.current === value) setError(null);
        } catch {
          if (!controller.signal.aborted && latest.current === value) {
            setError("Couldn’t save to your account. Your choice still applies on this browser.");
          }
        }
      }
    } finally {
      busy.current = false;
      if (!controller.signal.aborted) setSaving(false);
    }
  }

  function select(value: Preference) {
    revision.current += 1;
    latest.current = value;
    setTheme(value);
    setError(null);
    if (authenticated) {
      pending.current = value;
      void drain();
    }
  }

  return <Context.Provider value={{ select, error, saving, retry: () => {
    if (latest.current) {
      select(latest.current);
    } else {
      const controller = lifecycle.current;
      const before = revision.current;
      if (!controller || controller.signal.aborted) return;
      void apiFetch<Preferences>("/auth/me/preferences", { signal: controller.signal })
        .then((result) => {
          if (!controller.signal.aborted && revision.current === before) {
            setTheme(result.theme_preference);
            setError(null);
          }
        }).catch(() => { /* Keep the visible load error for another retry. */ });
    }
  } }}>{children}</Context.Provider>;
}
