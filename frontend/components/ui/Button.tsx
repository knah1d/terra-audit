import type { LucideIcon } from "lucide-react";
import { Loader2 } from "lucide-react";
import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANT_CLASSES: Record<Variant, string> = {
  // Pine-tinted shadow instead of neutral — reserved for primary actions,
  // the one place a brand-colored shadow reads as "premium" rather than
  // "why is this shadow green." Secondary/ghost/danger stay neutral.
  primary:
    "bg-brand-600 text-white shadow-glow-sm hover:bg-brand-700 hover:shadow-glow-md disabled:bg-brand-600/40 disabled:text-white/70 disabled:shadow-sm",
  secondary:
    "bg-surface border border-border text-text-primary shadow-sm hover:border-border-strong hover:bg-surface-muted disabled:text-text-tertiary",
  ghost: "text-text-secondary hover:bg-surface-muted hover:text-text-primary disabled:text-text-tertiary",
  danger: "bg-danger-600 text-white shadow-sm hover:bg-danger-700 disabled:bg-danger-600/40 disabled:text-white/70",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "px-3 py-1.5 text-[13px] gap-1.5",
  md: "px-4 py-2 text-sm gap-2",
};

export function Button({
  variant = "primary",
  size = "md",
  icon: Icon,
  loading = false,
  className = "",
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  icon?: LucideIcon;
  loading?: boolean;
}) {
  return (
    <button
      className={`press inline-flex items-center justify-center rounded-md font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 disabled:cursor-not-allowed ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : Icon && <Icon className="size-4" />}
      {children}
    </button>
  );
}
