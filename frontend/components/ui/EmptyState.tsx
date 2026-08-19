import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

/**
 * Replaces the bare "no data yet" text lines that used to appear in the
 * fields list, credit history table, etc. — a small icon + message +
 * optional action, consistent everywhere something is legitimately empty
 * (not an error, not loading).
 */
export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-6 py-10 text-center">
      <div className="flex size-10 items-center justify-center rounded-full bg-surface-muted text-text-tertiary">
        <Icon className="size-5" />
      </div>
      <p className="text-sm font-medium text-text-primary">{title}</p>
      {description && <p className="max-w-sm text-sm text-text-secondary">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
