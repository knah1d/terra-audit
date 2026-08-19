import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";
import { BotanicalMotif } from "@/components/ui/BotanicalMotif";
import { IconTile } from "@/components/ui/IconTile";

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
  motif = false,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  /** Opt-in botanical accent behind the icon tile — reserved for
   * non-data empty states (e.g. the fields list with zero fields).
   * Left off by default: this component is also used inside
   * CreditHistoryTable, a data screen the design boundary explicitly
   * keeps free of illustration. */
  motif?: boolean;
}) {
  return (
    <div className="enter relative flex flex-col items-center gap-2 overflow-hidden rounded-lg border border-dashed border-border px-6 py-10 text-center">
      {motif && (
        <BotanicalMotif
          size="sm"
          className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
        />
      )}
      <IconTile icon={Icon} tone={motif ? "brand" : "neutral"} />
      <p className="relative text-sm font-medium text-text-primary">{title}</p>
      {description && <p className="relative max-w-sm text-sm text-text-secondary">{description}</p>}
      {action && <div className="relative mt-2">{action}</div>}
    </div>
  );
}
