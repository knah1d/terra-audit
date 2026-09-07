"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useState } from "react";
import type { PortfolioEntry } from "@/types/api";

const FIELD_TYPE_LABELS: Record<string, string> = {
  rice_awd: "Rice — AWD (VM0051)",
  cropland_alm_vm0042: "Cropland — ALM (VM0042)",
};

/**
 * One horizontal bar per calculated field, colored by methodology — the
 * dataviz skill's categorical slots 1/2 (blue/orange), the same fixed pair
 * app.py's own Plotly chart used (rice_awd blue, cropland_alm_vm0042
 * orange). Only fields with a final_issuance actually appear — matching
 * app.py's own filter.
 */
export function PortfolioBarChart({ entries }: { entries: PortfolioEntry[] }) {
  const [hiddenTypes, setHiddenTypes] = useState<string[]>([]);
  const calculated = entries
    .filter((e) => e.final_issuance !== null && !hiddenTypes.includes(e.field_type))
    .map((e) => ({
      label: `${e.field_id} — ${e.name}`,
      value: e.final_issuance as number,
      fieldType: e.field_type,
    }));

  if (!entries.some((entry) => entry.final_issuance !== null)) return null;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondary">
        {Object.entries(FIELD_TYPE_LABELS).map(([type, label], index) => (
          <button key={type} type="button" aria-pressed={!hiddenTypes.includes(type)} onClick={() => setHiddenTypes((current) => current.includes(type) ? current.filter((item) => item !== type) : [...current, type])} className={`glass-control flex items-center gap-2 rounded-full px-3 py-2 transition-opacity ${hiddenTypes.includes(type) ? "opacity-50" : "opacity-100"}`}>
            <span className="size-2.5 rounded-full" style={{ background: `var(--chart-series-${index + 1})` }} />{label}
          </button>
        ))}
      </div>
      {calculated.length === 0 && <p role="status" className="py-8 text-center text-sm text-text-secondary">No calculated fields in the selected methodologies. Enable a methodology above.</p>}
      <div style={{ height: Math.max(280, 60 * calculated.length) }} className="w-full overflow-x-auto">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={calculated} layout="vertical" margin={{ left: 24, right: 16 }}>
            <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="2 4" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11, fill: "var(--chart-muted)" }} stroke="var(--chart-axis)" />
            <YAxis
              type="category"
              dataKey="label"
              width={200}
              tick={{ fontSize: 11, fill: "var(--chart-muted)" }}
              stroke="var(--chart-axis)"
            />
            <Tooltip
              contentStyle={{ background: "var(--surface)", border: "1px solid var(--border-c)", borderRadius: 8, fontSize: 12 }}
              formatter={(value, _name, item) => [
                `${Number(value).toFixed(4)} tCO2e`,
                FIELD_TYPE_LABELS[(item.payload as { fieldType: string }).fieldType] ?? "",
              ]}
            />
            <Bar dataKey="value" radius={4}>
              {calculated.map((entry, i) => (
                <Cell key={i} fill={entry.fieldType === "rice_awd" ? "var(--chart-series-1)" : "var(--chart-series-2)"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
