import type { LucideIcon } from "lucide-react";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import type { ButtonHTMLAttributes, ComponentProps } from "react";
import { resetLiquidPointer, trackLiquidPointer } from "@/components/ui/liquid-pointer";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "glass";
type Size = "sm" | "md" | "icon";
type Shape = "default" | "pill";

const VARIANT_CLASSES: Record<Variant, string> = {
  // Pine-tinted shadow instead of neutral — reserved for primary actions,
  // the one place a brand-colored shadow reads as "premium" rather than
  // "why is this shadow green." Secondary/ghost/danger stay neutral.
  // Primary/danger deliberately get NO liquid-hover: a moving reflection
  // on the one button making the page's key action would distract from
  // the label, not read as premium.
  primary:
    "primary-action disabled:shadow-none",
  danger: "bg-danger-600 text-white hover:bg-danger-700 active:bg-danger-700 disabled:bg-danger-600/40 disabled:text-white/70",
  // secondary/ghost/glass all get the liquid material (applied via the
  // `liquid-hover` class below, not here) — these three differ only in
  // their resting-state fill, since the hover glass looks the same on
  // top of any of them.
  secondary:
    "liquid-hover glass-control border border-border-default text-text-primary hover:border-border-strong disabled:text-text-tertiary",
  ghost: "liquid-hover text-text-secondary hover:text-text-primary disabled:text-text-tertiary",
  // Translucent at rest too (not just on hover) — a "glass" button should
  // read as glass even before the pointer arrives, unlike secondary/ghost
  // whose liquid-hover fade-in IS the only glass they show.
  glass:
    "liquid-hover liquid-active text-text-primary disabled:text-text-tertiary",
};

// md/icon meet the 44px control height; sm (36px) is for dense rows only.
const SIZE_CLASSES: Record<Size, string> = {
  sm: "min-h-9 px-3 text-[13px] gap-1.5",
  md: "min-h-11 px-4 text-sm gap-2",
  icon: "size-11 p-0",
};

const SHAPE_CLASSES: Record<Shape, string> = {
  default: "rounded-lg",
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
  if (process.env.NODE_ENV !== "production" && size === "icon" && !props["aria-label"] && !props["aria-labelledby"] && !props.title) {
    console.warn("Icon-only Button requires aria-label.");
  }
  // secondary/ghost/glass carry the `liquid-hover` class (see
  // VARIANT_CLASSES above) — only those get the pointer-tracked
  // reflection; primary/danger ignore these handlers entirely, so
  // wiring them unconditionally here is harmless (no-op on a button
  // without the .liquid-hover class) and keeps this simple rather than
  // branching per variant.
  const isLiquid = variant === "secondary" || variant === "ghost" || variant === "glass";

  return (
    <button
      className={`press inline-flex shrink-0 items-center justify-center whitespace-nowrap font-medium disabled:cursor-not-allowed ${SHAPE_CLASSES[shape]} ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      aria-busy={loading || undefined}
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
      {children != null && children !== false && <span className={size === "icon" ? "sr-only" : undefined}>{children}</span>}
    </button>
  );
}

/** Link styled as a Button — for navigation actions, so an <a> never wraps
 * a <button> (two tab stops, invalid nesting). */
export function ButtonLink({
  variant = "primary",
  size = "md",
  shape = "default",
  icon: Icon,
  className = "",
  children,
  ...props
}: ComponentProps<typeof Link> & { variant?: Variant; size?: Size; shape?: Shape; icon?: LucideIcon }) {
  return (
    <Link
      className={`press inline-flex shrink-0 items-center justify-center whitespace-nowrap font-medium ${SHAPE_CLASSES[shape]} ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      {...props}
    >
      {Icon && <Icon className="size-4" />}
      <span className={size === "icon" ? "sr-only" : undefined}>{children}</span>
    </Link>
  );
}
