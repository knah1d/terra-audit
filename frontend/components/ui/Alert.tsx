import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

type Tone = "info" | "success" | "warning" | "danger";

const TONE_STYLES: Record<Tone, { classes: string; Icon: typeof Info }> = {
  info: {
    classes: "border-info-600/20 bg-info-50 text-info-700",
    Icon: Info,
  },
  success: {
    classes: "border-success-600/20 bg-success-50 text-success-700",
    Icon: CheckCircle2,
  },
  warning: {
    classes: "border-warning-600/25 bg-warning-50 text-warning-700",
    Icon: AlertTriangle,
  },
  danger: {
    classes: "border-danger-600/20 bg-danger-50 text-danger-700",
    Icon: XCircle,
  },
};

/**
 * Shared tone banner — replaces every ad hoc red/amber <p>/<div> that used
 * to appear for form server-errors, parse errors, and blocking calculation
 * outcomes (QA3 pathway invalid, ALM leakage-blocked, incomplete practice
 * data). One visual language for every "something needs your attention."
 */
export function Alert({
  tone = "info",
  title,
  children,
  className = "",
}: {
  tone?: Tone;
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const { classes, Icon } = TONE_STYLES[tone];
  return (
    <div className={`flex gap-3 rounded-lg border px-4 py-3 text-sm ${classes} ${className}`}>
      <Icon className="mt-0.5 size-4 shrink-0" />
      <div className="flex flex-col gap-0.5">
        {title && <p className="font-medium">{title}</p>}
        <div className="text-[13px] leading-relaxed opacity-90">{children}</div>
      </div>
    </div>
  );
}
