import type { LucideIcon } from "lucide-react";
import { Loader2 } from "lucide-react";
import { ButtonHTMLAttributes } from "react";
import { resetLiquidPointer, trackLiquidPointer } from "@/components/ui/liquid-pointer";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "glass";
type Size = "sm" | "md";
type Shape = "default" | "pill";

const VARIANT_CLASSES: Record<Variant, string> = {
  // Pine-tinted shadow instead of neutral — reserved for primary actions,
  // the one place a brand-colored shadow reads as "premium" rather than
  // "why is this shadow green." Secondary/ghost/danger stay neutral.
  // Primary/danger deliberately get NO liquid-hover: a moving reflection
  // on the one button making the page's key action would distract from
  // the label, not read as premium.
  primary:
    "bg-brand-600 text-white shadow-glow-sm hover:bg-brand-700 hover:shadow-glow-md disabled:bg-brand-600/40 disabled:text-white/70 disabled:shadow-sm",
  danger: "bg-danger-600 text-white shadow-sm hover:bg-danger-700 disabled:bg-danger-600/40 disabled:text-white/70",
  // secondary/ghost/glass all get the liquid material (applied via the
  // `liquid-hover` class below, not here) — these three differ only in
  // their resting-state fill, since the hover glass looks the same on
  // top of any of them.
  secondary:
    "liquid-hover bg-surface border border-border text-text-primary shadow-sm hover:border-border-strong disabled:text-text-tertiary",
  ghost: "liquid-hover text-text-secondary hover:text-text-primary disabled:text-text-tertiary",
  // Translucent at rest too (not just on hover) — a "glass" button should
  // read as glass even before the pointer arrives, unlike secondary/ghost
  // whose liquid-hover fade-in IS the only glass they show.
  glass:
    "liquid-hover liquid-active text-text-primary disabled:text-text-tertiary",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "px-3 py-1.5 text-[13px] gap-1.5",
  md: "px-4 py-2 text-sm gap-2",
};

const SHAPE_CLASSES: Record<Shape, string> = {
  default: "rounded-md",
  pill: "rounded-full",
};

export function Button({
  variant = "primary",
  size = "md",
  shape = "default",
  icon: Icon,
  loading = false,
  className = "",
  children,
  disabled,
  onPointerEnter,
  onPointerMove,
  onPointerLeave,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  /** "pill" for compact toolbar/nav-style actions; "default" (rounded-md)
   * for normal form actions — kept as an opt-in prop so existing callers
   * are unaffected. */
  shape?: Shape;
  icon?: LucideIcon;
  loading?: boolean;
}) {
  // secondary/ghost/glass carry the `liquid-hover` class (see
  // VARIANT_CLASSES above) — only those get the pointer-tracked
  // reflection; primary/danger ignore these handlers entirely, so
  // wiring them unconditionally here is harmless (no-op on a button
  // without the .liquid-hover class) and keeps this simple rather than
  // branching per variant.
  const isLiquid = variant === "secondary" || variant === "ghost" || variant === "glass";

  return (
    <button
      className={`press inline-flex items-center justify-center font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 disabled:cursor-not-allowed ${SHAPE_CLASSES[shape]} ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      disabled={disabled || loading}
      onPointerEnter={(e) => {
        if (isLiquid) trackLiquidPointer(e);
        onPointerEnter?.(e);
      }}
      onPointerMove={(e) => {
        if (isLiquid) trackLiquidPointer(e);
        onPointerMove?.(e);
      }}
      onPointerLeave={(e) => {
        if (isLiquid) resetLiquidPointer(e);
        onPointerLeave?.(e);
      }}
      {...props}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : Icon && <Icon className="size-4" />}
      <span>{children}</span>
    </button>
  );
}
