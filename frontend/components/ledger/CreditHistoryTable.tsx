"use client";

import { useCreditHistory } from "@/hooks/use-carbon";
import { formatNumber } from "@/lib/format";

export function CreditHistoryTable({ fieldId }: { fieldId: string }) {
  const { data: history, isLoading } = useCreditHistory(fieldId);

  if (isLoading) return <p className="text-sm text-gray-500">Loading history…</p>;
  if (!history || history.length === 0) {
    return <p className="text-sm text-gray-500">No prior calculation runs recorded for this field.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
            <th className="py-2">Calculated At</th>
            <th className="py-2 text-right">Final Issuance (tCO2e)</th>
            {history.some((h) => h.result.cumulative_delta_co2_wp !== undefined) && (
              <th className="py-2 text-right">Cumulative SOC Δ (tCO2e)</th>
            )}
            <th className="py-2">Inputs</th>
          </tr>
        </thead>
        <tbody>
          {history.map((entry, i) => (
            <tr key={i} className="border-b border-gray-100">
              <td className="py-2 text-gray-600">{entry.calculated_at}</td>
              <td className="py-2 text-right font-mono tabular-nums">
                {formatNumber(entry.final_issuance, "tco2e")}
              </td>
              {history.some((h) => h.result.cumulative_delta_co2_wp !== undefined) && (
                <td className="py-2 text-right font-mono tabular-nums">
                  {entry.result.cumulative_delta_co2_wp !== undefined
                    ? formatNumber(entry.result.cumulative_delta_co2_wp as number, "tco2e")
                    : "—"}
                </td>
              )}
              <td className="py-2 text-xs text-gray-500">
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
