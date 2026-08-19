export function Card({
  children,
  className = "",
  variant = "solid",
  interactive = false,
}: {
  children: React.ReactNode;
  className?: string;
  /**
   * `solid` (default) keeps dense numeric content maximally legible and
   * avoids putting an expensive backdrop-filter on every list row.
   * `glass` is reserved for chrome — sticky panels, popovers, the auth
   * card. See the material note in app/globals.css.
   */
  variant?: "solid" | "glass";
  /** Adds hover-lift; use only for cards that are actually clickable. */
  interactive?: boolean;
}) {
  return (
    <div
      className={`rounded-lg p-5 ${variant === "glass" ? "glass-chrome" : "surface-card"} ${
        interactive ? "lift cursor-pointer" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "warning" | "success" | "danger";
}) {
  const toneClasses: Record<string, string> = {
    neutral: "text-text-primary",
    warning: "text-warning-700",
    success: "text-success-700",
    danger: "text-danger-700",
  };
  return (
    <Card className="flex flex-col gap-1.5 p-4">
      <span className="text-xs font-medium uppercase tracking-wide text-text-tertiary">{label}</span>
      <span className={`font-mono text-2xl font-semibold tracking-tight tabular-nums ${toneClasses[tone]}`}>
        {value}
      </span>
    </Card>
  );
}
