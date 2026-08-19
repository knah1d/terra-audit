"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

const OPTIONS = [
  { value: "light", label: "Light", icon: Sun },
  { value: "system", label: "System", icon: Monitor },
  { value: "dark", label: "Dark", icon: Moon },
] as const;

/**
 * Theme control — overrides the system preference for the session via
 * next-themes (persisted to localStorage).
 *
 * No `mounted` guard here on purpose: this is only ever reached through
 * the ssr:false dynamic wrapper in ThemeToggle.tsx, so by the time it
 * renders, next-themes' provider state has already resolved. The old
 * useState+useEffect mounted-guard tripped react-hooks/set-state-in-effect
 * and was solving a problem the wrapper solves more cleanly.
 */
export default function ThemeToggleControl() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="inline-flex gap-0.5 rounded-md bg-surface-muted p-0.5">
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          aria-label={label}
          aria-pressed={theme === value}
          onClick={() => setTheme(value)}
          className={`press flex size-7 items-center justify-center rounded-sm ${
            theme === value
              ? "bg-surface text-text-primary shadow-xs"
              : "text-text-tertiary hover:text-text-secondary"
          }`}
        >
          <Icon className="size-3.5" />
        </button>
      ))}
    </div>
  );
}
