"use client";

import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { resetLiquidPointer, trackLiquidPointer } from "@/components/ui/liquid-pointer";

export type TabOption<T extends string> = { value: T; label: string; icon?: LucideIcon };

/** A single glass indicator follows the selected segment, including after resizing. */
export function Tabs<T extends string>({ options, value, onChange }: {
  options: Array<TabOption<T>>;
  value: T;
  onChange: (value: T) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [indicator, setIndicator] = useState<{ left: number; top: number; width: number; height: number } | null>(null);
  useEffect(() => {
    const container = ref.current;
    if (!container) return;
    function measure() {
      const active = container?.querySelector<HTMLButtonElement>('[aria-pressed="true"]');
      if (active) setIndicator({ left: active.offsetLeft, top: active.offsetTop, width: active.offsetWidth, height: active.offsetHeight });
    }
    const frame = requestAnimationFrame(measure);
    const observer = new ResizeObserver(measure);
    observer.observe(container);
    for (const child of container.children) if (child.tagName === "BUTTON") observer.observe(child);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); };
  }, [value]);

  return (
    <div ref={ref} role="group" aria-label="View options" onKeyDown={event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key) || !(event.target instanceof HTMLButtonElement)) return;
      const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
      const current = buttons.indexOf(event.target);
      if (current < 0 || !buttons.length) return;
      event.preventDefault();
      const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (current + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
      buttons[next].focus();
    }} className="glass-chrome relative inline-flex max-w-full flex-wrap gap-1 rounded-xl p-1 text-sm">
      {indicator && <span aria-hidden className="pointer-events-none absolute rounded-lg bg-[var(--liquid-active-bg)] shadow-[inset_0_1px_0_var(--glass-specular)] transition-[left,top,width,height] duration-200" style={indicator} />}
      {options.map((opt) => {
        const Icon = opt.icon;
        const active = opt.value === value;
        return (
          <button key={opt.value} type="button" onClick={() => onChange(opt.value)}
            onPointerEnter={trackLiquidPointer} onPointerMove={trackLiquidPointer} onPointerLeave={resetLiquidPointer}
            aria-pressed={active}
            className={`liquid-hover press flex min-h-10 items-center gap-2 rounded-lg px-3 font-medium ${active ? "text-brand-700" : "text-text-secondary hover:text-text-primary"}`}>
            {Icon && <Icon className="size-3.5" aria-hidden />}<span>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
