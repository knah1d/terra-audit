"use client";

import { History, ListTree } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Sheet } from "@/components/ui/Sheet";
import { Skeleton } from "@/components/ui/Skeleton";
import { useCreditHistory } from "@/hooks/use-carbon";
import { formatNumber } from "@/lib/format";
import type { CreditHistoryEntry } from "@/types/api";

/** Renders a run's raw inputs as a clean key/value grid inside a Sheet —
 * replaces what used to be a "k=v, k=v, k=v" text dump inline in the
 * table, which was unreadable at a glance and didn't fit the row height. */
function ParametersSheet({ entry, onClose }: { entry: CreditHistoryEntry | null; onClose: () => void }) {
  return (
    <Sheet open={entry !== null} onClose={onClose} title="Calculation parameters">
      <dl className="grid grid-cols-2 gap-3 text-sm">
        {entry &&
          Object.entries(entry.inputs).map(([key, value]) => (
            <div key={key}>
              <dt className="text-xs uppercase tracking-wide text-text-tertiary">
                {key.replace(/_/g, " ")}
              </dt>
              <dd className="font-mono text-text-primary">{String(value)}</dd>
            </div>
          ))}
      </dl>
    </Sheet>
  );
}

export function CreditHistoryTable({ fieldId }: { fieldId: string }) {
  const { data: history, isLoading } = useCreditHistory(fieldId);
  const [inspecting, setInspecting] = useState<CreditHistoryEntry | null>(null);

  if (isLoading) return <Skeleton className="h-24" />;
  if (!history || history.length === 0) {
    return <EmptyState icon={History} title="No verification runs yet" description="Calculated carbon-credit results for this field will appear here." />;
  }

  const showCumulative = history.some((h) => h.result.cumulative_delta_co2_wp !== undefined);

  return (
    <>
      {/* rounded-xl + surface-card (not a plain border+rounded-lg) so this
       * reads as a floating list card — Apple Health's list-card treatment
       * rather than a spreadsheet. */}
      <div className="surface-card overflow-x-auto rounded-xl">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs font-medium uppercase tracking-wide text-text-tertiary">
              <th className="px-4 pb-2.5 pt-4">Calculated At</th>
              <th className="px-4 pb-2.5 pt-4 text-right">Final Issuance (tCO2e)</th>
              {showCumulative && <th className="px-4 pb-2.5 pt-4 text-right">Cumulative SOC Δ (tCO2e)</th>}
              <th className="px-4 pb-2.5 pt-4" />
            </tr>
          </thead>
          <tbody>
            {history.map((entry, i) => (
              <tr
                key={i}
                className="enter border-t border-border/60 transition-colors duration-[var(--dur-fast)] hover:bg-surface-muted/60"
                style={{ animationDelay: `${Math.min(i, 8) * 30}ms` }}
              >
                <td className="px-4 py-3.5 text-text-secondary">{entry.calculated_at}</td>
                <td className="px-4 py-3.5 text-right font-mono tabular-nums text-text-primary">
                  {formatNumber(entry.final_issuance, "tco2e")}
                </td>
                {showCumulative && (
                  <td className="px-4 py-3.5 text-right font-mono tabular-nums text-text-primary">
                    {entry.result.cumulative_delta_co2_wp !== undefined
                      ? formatNumber(entry.result.cumulative_delta_co2_wp as number, "tco2e")
                      : "—"}
                  </td>
                )}
                <td className="px-4 py-3.5 text-right">
                  <Button variant="ghost" size="sm" icon={ListTree} onClick={() => setInspecting(entry)}>
                    Parameters
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ParametersSheet entry={inspecting} onClose={() => setInspecting(null)} />
    </>
  );
}
