"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card } from "@/components/ui/Card";
import { Sheet } from "@/components/ui/Sheet";
import { Button } from "@/components/ui/Button";
import { Select, TextInput, TextArea } from "@/components/ui/Field";
import { apiFetch } from "@/lib/api";
import { formatDate, formatQueueTimestamp } from "@/lib/format";

type Sequence = { crop: string; start_date: string; end_date: string };
export type SeasonDetails = { name: string; crops: string[]; start_date: string; end_date: string; notes: string; season_type?: string; is_historical?: boolean; crop_sequence?: Sequence[]; intercrop_arrangement?: string; fallow_reason?: string; missing_period_reason?: string; version?: number; correction_reason?: string };
type Version = { id: string; created_at: string; payload: SeasonDetails };
export function SeasonHistory({ fieldId, seasonId, writable }: { fieldId: string; seasonId: string; writable: boolean }) {
  const base = `/fields/${fieldId}/crop-seasons/${seasonId}`;
  const client = useQueryClient();
  const [show, setShow] = useState(false); const [editing, setEditing] = useState(false);
  const versions = useQuery({ queryKey: ["season-versions", fieldId, seasonId], queryFn: () => apiFetch<Version[]>(`${base}/versions`), enabled: show || editing });
  const latest = versions.data?.at(-1);
  return <Card><h3 className="ui-subsection-title mb-3">Season corrections and history</h3><p className="ui-secondary mb-3">Corrections append a version with a reason. Existing observations and committed calculation snapshots retain their original provenance.</p><div className="flex flex-wrap gap-3"><Button variant="secondary" onClick={() => setShow(!show)}>{show ? "Hide history" : "View version history"}</Button>{writable && <Button variant="secondary" onClick={() => setEditing(true)}>Correct this season</Button>}</div>
    {(show || editing) && versions.isLoading && <p className="mt-3">Loading versions…</p>}{versions.error && <p role="alert" className="text-danger-700 mt-3">{versions.error.message}</p>}
    {show && versions.data?.map((v, index) => <div key={v.id} className="mt-3 border-t border-border pt-3"><p>Version {v.payload.version ?? index + 1} · {v.payload.name}</p><p className="ui-meta">{formatQueueTimestamp(v.created_at)} · {formatDate(v.payload.start_date)} to {formatDate(v.payload.end_date)} · {v.payload.crops.join(" + ") || v.payload.season_type}</p><p className="ui-secondary">{v.payload.correction_reason || "Original season record"}</p><details className="mt-2 ui-meta"><summary>Full stored record</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap break-words">{JSON.stringify(v.payload, null, 2)}</pre></details></div>)}
    <Sheet open={editing && !!latest} onClose={() => setEditing(false)} title="Correct crop season">
      {latest && <CorrectionForm key={latest.id} prior={latest.payload} base={base} onSaved={async () => { await client.invalidateQueries({ queryKey: ["crop-seasons", fieldId] }); await client.invalidateQueries({ queryKey: ["season-versions", fieldId, seasonId] }); await client.invalidateQueries({ queryKey: ["crop-evidence", fieldId] }); await client.invalidateQueries({ queryKey: ["ai-workspace"] }); setShow(true); setEditing(false); }} onCancel={() => setEditing(false)} />}
    </Sheet>
  </Card>;
}
function CorrectionForm({ prior, base, onSaved, onCancel }: { prior: SeasonDetails; base: string; onSaved: () => Promise<void>; onCancel: () => void }) {
  const [type, setType] = useState(prior.season_type ?? "single_crop"); const [sequence, setSequence] = useState(prior.crop_sequence ?? []); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const gap = type === "fallow" || type === "missing_period";
  return <form className="space-y-3" onSubmit={async e => {
    e.preventDefault(); const data = new FormData(e.currentTarget); setBusy(true); setError("");
    try {
      await apiFetch(`${base}/corrections`, { method: "POST", json: { name: data.get("name"), crops: gap ? [] : String(data.get("crops")).split(",").map(c => c.trim()).filter(Boolean), start_date: data.get("start_date"), end_date: data.get("end_date"), notes: data.get("notes"), season_type: type, is_historical: data.has("is_historical"), crop_sequence: ["rotation", "intercrop"].includes(type) ? sequence : [], intercrop_arrangement: String(data.get("intercrop_arrangement") ?? ""), fallow_reason: type === "fallow" ? data.get("gap_reason") : "", missing_period_reason: type === "missing_period" ? data.get("gap_reason") : "", reason: data.get("reason") } }); await onSaved();
    } catch (e) { setError(e instanceof Error ? e.message : "Correction failed"); } finally { setBusy(false); }
  }}>
    <fieldset disabled={busy} className="space-y-3"><label className="ui-label">Name<TextInput name="name" required maxLength={120} defaultValue={prior.name} /></label><label className="ui-label">Season type<Select value={type} onChange={e => setType(e.target.value)}>{["single_crop", "rotation", "intercrop", "cover_crop", "fallow", "missing_period"].map(t => <option key={t} value={t}>{t.replaceAll("_", " ")}</option>)}</Select></label>
    {!gap && <label className="ui-label">Crops, separated by commas<TextInput name="crops" required defaultValue={prior.crops.join(", ")} /></label>}
    <div className="grid gap-3 sm:grid-cols-2"><label className="ui-label">Start date<TextInput type="date" name="start_date" required defaultValue={prior.start_date} /></label><label className="ui-label">End date<TextInput type="date" name="end_date" required defaultValue={prior.end_date} /></label></div>
    <label className="flex items-center gap-2"><input type="checkbox" name="is_historical" defaultChecked={prior.is_historical} />Historical baseline season</label>
    {gap && <label className="ui-label">Reason for this period<TextArea name="gap_reason" required maxLength={500} defaultValue={type === "fallow" ? prior.fallow_reason : prior.missing_period_reason} /></label>}
    {type === "intercrop" && <label className="ui-label">Intercrop arrangement<TextInput name="intercrop_arrangement" maxLength={200} defaultValue={prior.intercrop_arrangement} /></label>}
    {["rotation", "intercrop"].includes(type) && <div className="space-y-3"><h4 className="ui-label">Crop sequence</h4>{sequence.map((entry, i) => <div key={i} className="grid gap-2 sm:grid-cols-3">{(["crop", "start_date", "end_date"] as const).map(key => <label key={key} className="ui-label">{key.replaceAll("_", " ")} {i + 1}<TextInput type={key === "crop" ? "text" : "date"} required value={entry[key]} onChange={e => setSequence(rows => rows.map((r, n) => n === i ? { ...r, [key]: e.target.value } : r))} /></label>)}<Button type="button" variant="ghost" onClick={() => setSequence(rows => rows.filter((_, n) => n !== i))}>Remove entry {i + 1}</Button></div>)}<Button type="button" variant="secondary" disabled={sequence.length >= 20} onClick={() => setSequence(rows => [...rows, { crop: "", start_date: prior.start_date, end_date: prior.end_date }])}>Add sequence entry</Button></div>}
    <label className="ui-label">Notes<TextArea name="notes" maxLength={2000} defaultValue={prior.notes} /></label><label className="ui-label">Correction reason<TextArea name="reason" required minLength={5} maxLength={2000} /></label></fieldset>
    {error && <p role="alert" className="text-danger-700">{error}</p>}<div className="flex gap-3"><Button type="submit" loading={busy}>Save corrected version</Button><Button type="button" variant="secondary" disabled={busy} onClick={onCancel}>Cancel</Button></div>
  </form>;
}
