import type { LucideIcon } from "lucide-react";
import { resetLiquidPointer, trackLiquidPointer } from "@/components/ui/liquid-pointer";

export type TabOption<T extends string> = {
  value: T;
  label: string;
  icon?: LucideIcon;
};

/**
 * Segmented control — extracted from what GeometryInputTabs used to
 * hand-roll once, now shared by any mode/tab switcher in the app.
 *
 * Liquid Glass treatment: the outer pill is a standard glass-chrome
 * capsule; each inactive option gets the pointer-following .liquid-hover
 * material on hover/focus, the active option keeps a stable
 * brand-tinted .liquid-active capsule (not a flat `bg-surface` block) —
 * "lit from within" rather than a plain segmented-control look.
 */
export function Tabs<T extends string>({
  options,
  value,
  onChange,
}: {
  options: Array<TabOption<T>>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="glass-chrome inline-flex gap-1 rounded-full p-1 text-sm">
      {options.map((opt) => {
        const Icon = opt.icon;
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            onPointerEnter={trackLiquidPointer}
            onPointerMove={trackLiquidPointer}
            onPointerLeave={resetLiquidPointer}
            aria-current={active ? "true" : undefined}
            className={`liquid-hover press flex items-center gap-1.5 rounded-full px-3 py-1.5 font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 ${
              active ? "liquid-active text-brand-700" : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {Icon && <Icon className="size-3.5" />}
            <span>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
