export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-lg border border-gray-200 bg-white p-4 shadow-sm ${className}`}>
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
    neutral: "text-gray-900",
    warning: "text-amber-700",
    success: "text-emerald-700",
    danger: "text-red-700",
  };
  return (
    <Card className="flex flex-col gap-1">
      <span className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</span>
      <span className={`font-mono text-2xl font-semibold tabular-nums ${toneClasses[tone]}`}>
        {value}
      </span>
    </Card>
  );
}
