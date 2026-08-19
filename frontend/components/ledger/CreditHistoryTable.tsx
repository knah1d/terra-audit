"use client";

import { History } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useCreditHistory } from "@/hooks/use-carbon";
import { formatNumber } from "@/lib/format";

export function CreditHistoryTable({ fieldId }: { fieldId: string }) {
  const { data: history, isLoading } = useCreditHistory(fieldId);

  if (isLoading) return <Skeleton className="h-24" />;
  if (!history || history.length === 0) {
    return <EmptyState icon={History} title="No verification runs yet" description="Calculated carbon-credit results for this field will appear here." />;
  }

  const showCumulative = history.some((h) => h.result.cumulative_delta_co2_wp !== undefined);

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-surface-muted text-left text-xs font-medium uppercase tracking-wide text-text-tertiary">
            <th className="px-3 py-2.5">Calculated At</th>
            <th className="px-3 py-2.5 text-right">Final Issuance (tCO2e)</th>
            {showCumulative && <th className="px-3 py-2.5 text-right">Cumulative SOC Δ (tCO2e)</th>}
            <th className="px-3 py-2.5">Inputs</th>
          </tr>
        </thead>
        <tbody>
          {history.map((entry, i) => (
            <tr key={i} className="border-b border-border last:border-0 hover:bg-surface-muted/60">
              <td className="px-3 py-2.5 text-text-secondary">{entry.calculated_at}</td>
              <td className="px-3 py-2.5 text-right font-mono tabular-nums text-text-primary">
                {formatNumber(entry.final_issuance, "tco2e")}
              </td>
              {showCumulative && (
                <td className="px-3 py-2.5 text-right font-mono tabular-nums text-text-primary">
                  {entry.result.cumulative_delta_co2_wp !== undefined
                    ? formatNumber(entry.result.cumulative_delta_co2_wp as number, "tco2e")
                    : "—"}
                </td>
              )}
              <td className="px-3 py-2.5 text-xs text-text-tertiary">
                {Object.entries(entry.inputs)
                  .map(([k, v]) => `${k}=${v}`)
                  .join(", ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
