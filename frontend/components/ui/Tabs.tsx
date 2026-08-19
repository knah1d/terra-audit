import type { LucideIcon } from "lucide-react";

export type TabOption<T extends string> = {
  value: T;
  label: string;
  icon?: LucideIcon;
};

/**
 * Segmented control — extracted from what GeometryInputTabs used to
 * hand-roll once, now shared by any mode/tab switcher in the app.
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
    <div className="inline-flex gap-1 rounded-lg bg-surface-muted p-1 text-sm">
      {options.map((opt) => {
        const Icon = opt.icon;
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`press flex items-center gap-1.5 rounded-sm px-3 py-1.5 font-medium ${
              active
                ? "bg-surface text-text-primary shadow-xs"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {Icon && <Icon className="size-3.5" />}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
