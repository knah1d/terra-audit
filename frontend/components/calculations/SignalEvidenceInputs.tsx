"use client";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { formatDate, formatQueueTimestamp } from "@/lib/format";
import { Select } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { useState } from "react";

type Evidence = { job_id: string; finished_at: string | null; window_start: string; window_end: string; area_ha: number; total_awd: number; season_length_days: number; detector_used: string };
export function SignalEvidenceInputs({ fieldId, area, start, end, disabled, onSelect }: {
  fieldId: string; area: number | null; start: string; end: string; disabled: boolean; onSelect: (id: string) => void;
}) {
  const query = useQuery({ queryKey: ["signal-evidence", fieldId], queryFn: () => apiFetch<Evidence[]>(`/fields/${encodeURIComponent(fieldId)}/signal-runs/evidence`) });
  const [selected, setSelected] = useState("");
  const [used, setUsed] = useState("");
  const compatible = (query.data ?? []).filter(row => row.window_start === start && row.window_end === end && area != null && Math.abs(row.area_ha - area) <= Math.max(1e-9, Math.abs(area) * 1e-9) && Number.isFinite(row.total_awd) && Number.isFinite(row.season_length_days));
  return <section className="rounded-lg border border-border p-3 sm:col-span-2 space-y-2" aria-label="Saved analytics input evidence">
    <h4 className="ui-subsection-title">Use saved analytics</h4>
    <p className="ui-meta">Only runs matching this field, registered area and both monitoring dates are offered. Confirm that the boundary and selected crop seasons match: older signal jobs do not freeze those versions. Nitrogen, water regime and amendments remain manual.</p>
    {query.isPending ? <p role="status">Loading saved runs…</p> : query.isError ? <p role="alert">Saved runs unavailable: {query.error.message}</p> : !compatible.length ? <p className="ui-secondary">No compatible run among recent completed analytics. Run analytics for {formatDate(start)} to {formatDate(end)}, or enter documented values manually.</p> : <>
      <Select aria-label="Saved analytics run" disabled={disabled} value={selected} onChange={e => setSelected(e.target.value)}><option value="">Select a completed run</option>{compatible.map(row => <option key={row.job_id} value={row.job_id}>{formatQueueTimestamp(row.finished_at)} · {row.detector_used} · {row.job_id.slice(0, 8)}</option>)}</Select>
      <Button type="button" size="sm" variant="secondary" disabled={disabled || !selected} onClick={event => {
        const row = compatible.find(item => item.job_id === selected);
        const form = event.currentTarget.closest("form");
        if (!row || !form) return;
        for (const [name, value] of [["awd_events", row.total_awd], ["season_length_days", row.season_length_days]] as const) {
          const input = form.elements.namedItem(name) as HTMLInputElement | null;
          if (input) { input.value = String(value); input.dispatchEvent(new Event("input", { bubbles: true })); input.dispatchEvent(new Event("change", { bubbles: true })); }
        }
        const confirmation = form.elements.namedItem("evidence_confirmed") as HTMLInputElement | null;
        if (confirmation) confirmation.checked = false;
        setUsed(row.job_id); onSelect(row.job_id);
      }}>Use AWD and season length from this run</Button>
    </>}
    {used && <p role="status" className="ui-meta break-all">Input source: {used}. You may edit the values; changed values are recorded as overrides in the saved snapshot.</p>}
    <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => { setUsed(""); onSelect(""); }}>Keep values as manual entry</Button>
  </section>;
}
