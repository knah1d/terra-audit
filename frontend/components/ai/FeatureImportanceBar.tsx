"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AiFeatureImportance } from "@/types/api";

/** Horizontal bar, single hue (one series, no identity to distinguish —
 * the dataviz skill's rule that a single series needs no legend/hue
 * variation). Values arrive pre-sorted descending from the backend. */
export function FeatureImportanceBar({ importance }: { importance: AiFeatureImportance }) {
  const data = Object.entries(importance)
    .slice(0, 12)
    .map(([name, value]) => ({ name, value }))
    .reverse(); // Recharts vertical-layout bars render bottom-up

  return (
    <div style={{ height: Math.max(200, 28 * data.length) }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="2 4" horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 11, fill: "var(--chart-muted)" }} stroke="var(--chart-axis)" />
          <YAxis
            type="category"
            dataKey="name"
            width={140}
            tick={{ fontSize: 11, fill: "var(--chart-muted)" }}
            stroke="var(--chart-axis)"
          />
          <Tooltip
            contentStyle={{ background: "var(--surface)", border: "1px solid var(--border-c)", borderRadius: 8, fontSize: 12 }}
            formatter={(value) => Number(value).toFixed(4)}
          />
          <Bar dataKey="value" fill="var(--chart-series-1)" radius={4} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
