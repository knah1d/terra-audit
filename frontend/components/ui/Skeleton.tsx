import { Loader2 } from "lucide-react";

/** Replaces every literal "Loading…" string with a consistent shimmer block. */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-surface-muted ${className}`} />;
}

/** Inline spinner + label, for buttons and small in-place loading states. */
export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-text-secondary">
      <Loader2 className="size-4 animate-spin" />
      {label}
    </span>
  );
}
