"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Select } from "@/components/ui/Field";
import { apiFetch } from "@/lib/api";
import { formatDate } from "@/lib/format";

type Run = { job_id: string; window_start: string; window_end: string; total_awd: number };
type Season = { id: string; payload: { name: string; start_date: string; end_date: string } };

/** Picks a saved rule-based Signal Analytics run and fills the monitoring
 * period with its exact window plus the crop seasons that overlap it, so
 * dates are not typed again. The backend still requires an exact match
 * before a run's values can be used (src/carbon/signal_evidence.py). */
export function StartFromRun({ fieldId, seasons, disabled, onPick }: {
  fieldId: string;
  seasons: Season[];
  disabled: boolean;
  onPick: (start: string, end: string, seasonIds: string[]) => void;
}) {
  const runs = useQuery({
    queryKey: ["signal-evidence", fieldId],
    queryFn: () => apiFetch<Run[]>(`/fields/${encodeURIComponent(fieldId)}/signal-runs/evidence`),
  });
  const [picked, setPicked] = useState("");
  const run = runs.data?.find((r) => r.job_id === picked);
  const overlapping = run ? seasons.filter((s) => s.payload.start_date <= run.window_end && s.payload.end_date >= run.window_start) : [];
  const covered = run && overlapping.length > 0
    && overlapping.some((s) => s.payload.start_date <= run.window_start)
    && overlapping.some((s) => s.payload.end_date >= run.window_end);

  if (!runs.data?.length) return null;
  return (
    <div>
      <label className="block">Start from a saved Signal Analytics run
        <Select value={picked} disabled={disabled} onChange={(e) => {
          setPicked(e.target.value);
          const r = runs.data?.find((x) => x.job_id === e.target.value);
          if (!r) return;
          const ids = seasons.filter((s) => s.payload.start_date <= r.window_end && s.payload.end_date >= r.window_start).map((s) => s.id);
          onPick(r.window_start, r.window_end, ids);
        }}>
          <option value="">Choose a run (or enter dates below)</option>
          {runs.data.map((r) => (
            <option key={r.job_id} value={r.job_id}>{formatDate(r.window_start)} – {formatDate(r.window_end)} · {r.total_awd} AWD events</option>
          ))}
        </Select>
      </label>
      {run && !covered && (
        <p role="status" className="mt-1 text-sm text-warning-700">The crop seasons do not fully cover this run&apos;s window — readiness will flag it.</p>
      )}
    </div>
  );
}
