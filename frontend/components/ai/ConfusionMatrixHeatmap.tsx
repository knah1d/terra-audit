/**
 * Confusion matrix as a small HTML/CSS grid, not a Recharts chart — a
 * heatmap of discrete labeled cells reads better as a styled table than
 * as a chart primitive, and it needs precise per-cell text overlay
 * (predicted-vs-actual counts) that a chart library fights rather than
 * helps with. Sequential encoding (one hue, light→dark) per the dataviz
 * skill's magnitude rule — intensity mapped to each cell's share of the
 * matrix's max count.
 */
export function ConfusionMatrixHeatmap({ labels, matrix }: { labels: string[]; matrix: number[][] }) {
  const max = Math.max(1, ...matrix.flat());

  function bg(value: number): string {
    const t = value / max; // 0..1
    if (t === 0) return "var(--surface-muted)";
    const steps = ["var(--chart-seq-100)", "var(--chart-seq-300)", "var(--chart-seq-500)", "var(--chart-seq-700)"];
    const idx = Math.min(steps.length - 1, Math.floor(t * steps.length));
    return steps[idx];
  }

  function textColor(value: number): string {
    return value / max > 0.5 ? "#ffffff" : "var(--text-primary)";
  }

  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-1 text-xs">
        <thead>
          <tr>
            <th></th>
            <th colSpan={labels.length} className="pb-1 text-center font-medium text-text-tertiary">
              Predicted
            </th>
          </tr>
          <tr>
            <th className="pr-1 text-right font-medium text-text-tertiary">Actual</th>
            {labels.map((l) => (
              <th key={l} className="w-20 truncate px-1 pb-1 text-center font-medium text-text-tertiary">
                {l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <th className="pr-2 text-right font-medium text-text-tertiary">{labels[i]}</th>
              {row.map((value, j) => (
                <td
                  key={j}
                  className="h-12 w-20 rounded-md text-center font-mono tabular-nums"
                  style={{ background: bg(value), color: textColor(value) }}
                >
                  {value}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
