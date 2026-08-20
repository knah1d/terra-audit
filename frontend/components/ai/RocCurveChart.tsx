"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { AiRocCurveData } from "@/types/api";

const SERIES_VARS = ["--chart-series-1", "--chart-series-2", "--chart-series-3", "--chart-series-4"];
const CHANCE_LINE = [{ fpr: 0, tpr: 0 }, { fpr: 1, tpr: 1 }];

/** One-vs-rest ROC per class — each Line carries its own `data` (fpr/tpr
 * pairs), since classes don't share a common x-axis sample grid. A class
 * with `auc: null` (too few samples in the fold to compute it, a real,
 * flagged occurrence per src/ai/evaluate.py) still plots but its legend
 * label says "AUC: N/A" rather than hiding the curve. */
export function RocCurveChart({ roc }: { roc: AiRocCurveData }) {
  const classes = Object.keys(roc);

  return (
    <div className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="2 4" />
          <XAxis
            dataKey="fpr"
            type="number"
            domain={[0, 1]}
            tick={{ fontSize: 11, fill: "var(--chart-muted)" }}
            stroke="var(--chart-axis)"
            label={{ value: "False Positive Rate", position: "insideBottom", fontSize: 11, fill: "var(--chart-muted)", offset: -4 }}
          />
          <YAxis
            dataKey="tpr"
            type="number"
            domain={[0, 1]}
            tick={{ fontSize: 11, fill: "var(--chart-muted)" }}
            stroke="var(--chart-axis)"
            width={44}
          />
          <Tooltip
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--border-c)", borderRadius: 8, fontSize: 12 }}
            formatter={(value) => Number(value).toFixed(3)}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line
            name="Chance"
            data={CHANCE_LINE}
            dataKey="tpr"
            stroke="var(--chart-axis)"
            strokeDasharray="4 4"
            dot={false}
            isAnimationActive={false}
          />
          {classes.map((cls, i) => {
            const curve = roc[cls];
            const points = curve.fpr.map((fpr, idx) => ({ fpr, tpr: curve.tpr[idx] }));
            const aucLabel = curve.auc !== null ? curve.auc.toFixed(3) : "N/A";
            return (
              <Line
                key={cls}
                name={`${cls} (AUC: ${aucLabel})`}
                data={points}
                dataKey="tpr"
                stroke={`var(${SERIES_VARS[i % SERIES_VARS.length]})`}
                strokeWidth={2}
                dot={false}
              />
            );
          })}
        </LineChart>
      </ResponsiveContainer>
      {classes.some((c) => roc[c].auc === null) && (
        <p className="mt-1 text-xs text-text-tertiary">
          A class with too few samples in a fold shows AUC: N/A — its curve isn&apos;t statistically meaningful.
        </p>
      )}
    </div>
  );
}
