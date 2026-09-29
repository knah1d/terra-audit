export function Card({
  children,
  className = "",
  variant = "solid",
  interactive = false,
}: {
  children: React.ReactNode;
  className?: string;
  /** Content and chrome both use frosted materials; glass adds a brighter rim. */
  variant?: "solid" | "glass";
  /** Adds hover/active states; use only for cards that are actually clickable. */
  interactive?: boolean;
}) {
  return (
    <div
      className={`ui-card ${variant === "glass" ? "glass-chrome" : ""} ${
        interactive ? "ui-card-interactive" : ""
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
    <Card className="flex flex-col gap-2">
      <span className="ui-meta font-medium uppercase tracking-wide">{label}</span>
      <span className={`break-words font-mono text-xl xl:text-2xl font-semibold tracking-tight tabular-nums ${toneClasses[tone]}`}>
        {value}
      </span>
    </Card>
  );
}
