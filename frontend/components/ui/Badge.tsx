type Tone = "neutral" | "brand" | "success" | "warning" | "danger";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-surface-muted text-text-secondary border-border",
  brand: "bg-brand-50 text-brand-700 border-brand-600/20",
  success: "bg-success-50 text-success-700 border-success-600/20",
  warning: "bg-warning-50 text-warning-700 border-warning-600/20",
  danger: "bg-danger-50 text-danger-700 border-danger-600/20",
};

/** Small pill for field-type labels, roles, and status tags. */
export function Badge({
  tone = "neutral",
  children,
  className = "",
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
