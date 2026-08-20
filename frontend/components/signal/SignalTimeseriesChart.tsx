"use client";

import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ResponsiveContainer } from "recharts";

interface Row {
  date: string;
  vv?: number;
  vv_smoothed?: number;
  vh_smoothed?: number;
  is_sowing?: number;
  is_harvest?: number;
}

/**
 * VV/VH backscatter chart — the frontend analogue of app.py's Plotly figure
 * in render_signal_analytics_tab: raw VV (faded scatter, the "flooding
 * proxy" is the smoothed line, not the raw points), smoothed VV line,
 * smoothed VH dashed line ("phenology proxy"), a vertical reference line
 * per AWD drydown date. Chart palette per the dataviz skill's validated
 * categorical order (globals.css --chart-series-*), not the brand ramp —
 * two lines need to be tell-apart-able independent of hue-only judgment,
 * which is why each also gets a distinct dash pattern.
 */
export function SignalTimeseriesChart({ rows, awdDates }: { rows: Row[]; awdDates: string[] }) {
  const sowing = rows.find((r) => r.is_sowing);
  const harvest = rows.find((r) => r.is_harvest);

  return (
    <div className="h-[360px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: "var(--chart-muted)" }}
            stroke="var(--chart-axis)"
            minTickGap={32}
          />
          <YAxis tick={{ fontSize: 11, fill: "var(--chart-muted)" }} stroke="var(--chart-axis)" width={44} />
          <Tooltip
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border-c)",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--text-primary)" }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Scatter name="VV (raw)" dataKey="vv" fill="var(--chart-muted)" opacity={0.35} r={2} />
          <Line
            name="VV smoothed (flooding proxy)"
            type="monotone"
            dataKey="vv_smoothed"
            stroke="var(--chart-series-1)"
            strokeWidth={2}
            dot={false}
          />
          <Line
            name="VH smoothed (phenology proxy)"
            type="monotone"
            dataKey="vh_smoothed"
            stroke="var(--chart-series-2)"
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
          />
          {awdDates.map((d) => (
            <ReferenceLine
              key={d}
              x={d}
              stroke="var(--chart-series-4)"
              strokeDasharray="3 3"
              label={{ value: "AWD", position: "top", fontSize: 10, fill: "var(--chart-series-4)" }}
            />
          ))}
          {sowing && (
            <ReferenceLine
              x={sowing.date}
              stroke="var(--chart-series-3)"
              label={{ value: "Sowing", position: "insideTopLeft", fontSize: 10, fill: "var(--chart-series-3)" }}
            />
          )}
          {harvest && (
            <ReferenceLine
              x={harvest.date}
              stroke="var(--danger-600)"
              label={{ value: "Harvest", position: "insideTopRight", fontSize: 10, fill: "var(--danger-600)" }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
