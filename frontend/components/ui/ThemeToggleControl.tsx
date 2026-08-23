"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { resetLiquidPointer, trackLiquidPointer } from "@/components/ui/liquid-pointer";

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
    <div className="inline-flex gap-0.5 rounded-full bg-surface p-0.5 shadow-xs">
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          aria-label={label}
          aria-pressed={theme === value}
          onClick={() => setTheme(value)}
          onPointerEnter={trackLiquidPointer}
          onPointerMove={trackLiquidPointer}
          onPointerLeave={resetLiquidPointer}
          className={`liquid-hover press flex size-7 items-center justify-center rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 ${
            theme === value
              ? "liquid-active text-brand-700"
              : "text-text-tertiary hover:text-text-secondary"
          }`}
        >
          {/* A selected icon settling in with a small rotate is a nicer
           * "this just switched" cue than a flat color swap alone. */}
          <Icon
            className={`size-3.5 transition-transform duration-[var(--dur-slow)] ease-[var(--curve-out)] ${
              theme === value ? "rotate-0" : "rotate-[-25deg]"
            }`}
          />
        </button>
      ))}
    </div>
  );
}
