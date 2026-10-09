import { Badge } from "@/components/ui/Badge";
import type { StepStatus } from "@/types/api";

export const STATUS_META: Record<StepStatus, { label: string; tone: "neutral" | "brand" | "warning" | "success" | "danger"; dot: string }> = {
  not_started: { label: "Not started", tone: "neutral", dot: "bg-text-tertiary/50" },
  in_progress: { label: "In progress", tone: "brand", dot: "bg-brand-600" },
  needs_attention: { label: "Needs attention", tone: "warning", dot: "bg-warning-600" },
  ready: { label: "Ready", tone: "success", dot: "bg-success-600" },
  completed: { label: "Completed", tone: "success", dot: "bg-success-600" },
  not_applicable: { label: "Not applicable", tone: "neutral", dot: "bg-transparent border border-text-tertiary/50" },
};

export function StepStatusBadge({ status }: { status: StepStatus }) {
  return <Badge tone={STATUS_META[status].tone}>{STATUS_META[status].label}</Badge>;
}

export function StepStatusDot({ status }: { status: StepStatus }) {
  return (
    <span title={STATUS_META[status].label} className={`inline-block size-2 shrink-0 rounded-full ${STATUS_META[status].dot}`}>
      <span className="sr-only">{STATUS_META[status].label}</span>
    </span>
  );
}
