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
    <div ref={ref} className="glass-chrome relative inline-flex max-w-full flex-wrap gap-1 rounded-2xl p-1 text-sm">
      {indicator && <span aria-hidden className="pointer-events-none absolute rounded-xl bg-[var(--liquid-active-bg)] shadow-[inset_0_1px_0_var(--glass-specular)] transition-[left,top,width,height] duration-200" style={indicator} />}
      {options.map((opt) => {
        const Icon = opt.icon;
        const active = opt.value === value;
        return (
          <button key={opt.value} type="button" onClick={() => onChange(opt.value)}
            onPointerEnter={trackLiquidPointer} onPointerMove={trackLiquidPointer} onPointerLeave={resetLiquidPointer}
            aria-pressed={active}
            className={`liquid-hover press flex items-center gap-1.5 rounded-xl px-3 py-2 font-medium ${active ? "text-brand-700" : "text-text-secondary hover:text-text-primary"}`}>
            {Icon && <Icon className="size-3.5" />}<span>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
