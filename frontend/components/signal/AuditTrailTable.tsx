/**
 * Per-observation "Compliance Audit Trail Ledger" — the frontend analogue
 * of app.py's st.dataframe with column_config formatting. A plain table
 * (not DerivationTrail, which is for a fixed formula sequence, not a
 * scrollable per-row dataset).
 */
export function AuditTrailTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  const hasAiColumns = rows.some((r) => "predicted_label" in r);

  function fmt(v: unknown, decimals = 4): string {
    if (typeof v === "number") return v.toFixed(decimals);
    if (typeof v === "boolean") return v ? "✓" : "";
    if (v === null || v === undefined) return "—";
    return String(v);
  }

  return (
    <div className="surface-card max-h-[420px] overflow-auto rounded-xl">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-surface">
          <tr className="text-left text-xs font-medium uppercase tracking-wide text-text-tertiary">
            <th className="px-3 pb-2.5 pt-3">Date</th>
            <th className="px-3 pb-2.5 pt-3 text-right">VV smoothed</th>
            <th className="px-3 pb-2.5 pt-3 text-right">VH smoothed</th>
            <th className="px-3 pb-2.5 pt-3 text-right">VV z-score</th>
            <th className="px-3 pb-2.5 pt-3 text-center">Flooded</th>
            <th className="px-3 pb-2.5 pt-3 text-center">Drydown</th>
            <th className="px-3 pb-2.5 pt-3 text-center">Sowing</th>
            <th className="px-3 pb-2.5 pt-3 text-center">Harvest</th>
            {hasAiColumns && <th className="px-3 pb-2.5 pt-3">Predicted</th>}
            {hasAiColumns && <th className="px-3 pb-2.5 pt-3 text-right">Confidence</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border/60">
              <td className="px-3 py-2 text-text-secondary">{fmt(r.date, 0)}</td>
              <td className="px-3 py-2 text-right font-mono tabular-nums">{fmt(r.vv_smoothed)}</td>
              <td className="px-3 py-2 text-right font-mono tabular-nums">{fmt(r.vh_smoothed)}</td>
              <td className="px-3 py-2 text-right font-mono tabular-nums">{fmt(r.vv_zscore, 3)}</td>
              <td className="px-3 py-2 text-center">{fmt(Boolean(r.is_flooded), 0)}</td>
              <td className="px-3 py-2 text-center">{fmt(Boolean(r.drydown_event), 0)}</td>
              <td className="px-3 py-2 text-center">{fmt(Boolean(r.is_sowing), 0)}</td>
              <td className="px-3 py-2 text-center">{fmt(Boolean(r.is_harvest), 0)}</td>
              {hasAiColumns && <td className="px-3 py-2 text-text-secondary">{fmt(r.predicted_label, 0)}</td>}
              {hasAiColumns && (
                <td className="px-3 py-2 text-right font-mono tabular-nums">
                  {typeof r.confidence === "number" ? `${(r.confidence * 100).toFixed(1)}%` : "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
