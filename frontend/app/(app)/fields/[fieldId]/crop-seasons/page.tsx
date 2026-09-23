"use client";

import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/app/providers";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput } from "@/components/ui/Field";
import { apiFetch } from "@/lib/api";

type RecordRow<T> = { id: string; season_id: string; created_at: string; payload: T };
type Season = {
  name: string; crops: string[]; start_date: string; end_date: string; notes: string;
  season_type?: string; is_historical?: boolean; fallow_reason?: string; missing_period_reason?: string;
};
type Observation = { kind: string; value: string; numeric_value: number | null; unit: string | null; source: string; observed_at: string; evidence_reference: string; created_by: string };
type Review = { observation_id: string; decision: string; reason: string; reviewed_by: string };
type Run = { processing_version: string; quality: { status: string; warnings: string[]; sensors: Record<string, { usable_dates: number; max_gap_days: number }> } };
type Evidence = { observations: RecordRow<Observation>[]; reviews: RecordRow<Review>[]; runs: RecordRow<Run>[]; sha256: string };
type Corpus = { examples: { crop: string }[]; excluded: { season_id: string; reason: string }[]; sha256: string };
type Benchmark = { classes: string[]; split: string; models: Record<string, { report: { accuracy: number; "macro avg": { f1: number } }; log_loss: number; brier_score: number }>; limitations: string[] };
type Job = { job_id: string; status: string; error: string | null; result: Benchmark | { run_id: string } | null };

function download(value: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const a = document.createElement("a"); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url);
}

export default function CropSeasonsPage() {
  const field = useFieldContext();
  const session = useSession();
  const writable = session?.role === "admin" || session?.role === "analyst";
  const queryClient = useQueryClient();
  const base = `/fields/${encodeURIComponent(field.field_id)}/crop-seasons`;
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [kind, setKind] = useState("crop_identity");
  const [seasonType, setSeasonType] = useState("single_crop");
  const [isHistorical, setIsHistorical] = useState(false);
  const [split, setSplit] = useState("field");
  const seasons = useQuery({ queryKey: ["crop-seasons", field.field_id], queryFn: () => apiFetch<RecordRow<Season>[]>(base) });
  const seasonId = selected || seasons.data?.[0]?.id || "";
  const path = `${base}/${seasonId}`;
  const evidence = useQuery({ queryKey: ["crop-evidence", field.field_id, seasonId], queryFn: () => apiFetch<Evidence>(`${path}/evidence`), enabled: !!seasonId });
  const corpus = useQuery({ queryKey: ["crop-corpus"], queryFn: () => apiFetch<Corpus>("/multi-crop/dataset") });
  const history = useQuery({ queryKey: ["crop-benchmarks"], queryFn: () => apiFetch<{ job_id: string; split: string; dataset_sha256: string }[]>("/multi-crop/benchmarks") });
  const job = useQuery({ queryKey: ["crop-job", jobId], queryFn: () => apiFetch<Job>(`/multi-crop/jobs/${jobId}`), enabled: !!jobId,
    refetchInterval: q => ["done", "error"].includes(q.state.data?.status ?? "") ? false : 1500 });
  const running = !!jobId && !job.error && !["done", "error"].includes(job.data?.status ?? "");
  useEffect(() => {
    if (job.data?.status === "done") {
      void queryClient.invalidateQueries({ queryKey: ["crop-evidence"] });
      void queryClient.invalidateQueries({ queryKey: ["crop-corpus"] });
      void queryClient.invalidateQueries({ queryKey: ["crop-benchmarks"] });
    }
  }, [job.data?.status, queryClient]);

  async function perform(action: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Unable to complete this action"); }
    finally { setBusy(false); }
  }

  const latest = evidence.data?.runs.at(-1);
  const result = job.data?.result && "models" in job.data.result ? job.data.result : null;
  const numeric = kind === "water_level" || kind === "residue_cover";

  return <div className="space-y-5">
    <div>
      <h2 className="text-lg font-semibold">Crop seasons & evidence</h2>
      <p className="mt-1 text-sm text-text-secondary">Record any crop or crop mixture, collect observations, and explore satellite coverage. These records support both accounting pathways; they do not change the field’s carbon methodology.</p>
    </div>
    {(error || seasons.error || evidence.error || corpus.error || job.error || job.data?.error) && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{error || seasons.error?.message || evidence.error?.message || corpus.error?.message || job.error?.message || job.data?.error}</p>}
    {notice && <p role="status" className="text-sm text-success-700">{notice}</p>}
    {writable && <Card>
      <h3 className="mb-3 font-medium">Add a crop season</h3>
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={e => {
        e.preventDefault(); const form = e.currentTarget; const data = new FormData(form);
        const isGap = seasonType === "fallow" || seasonType === "missing_period";
        void perform(async () => {
          const row = await apiFetch<RecordRow<Season>>(base, { method: "POST", json: {
            name: data.get("name"),
            crops: isGap ? [] : String(data.get("crops")).split(","),
            start_date: data.get("start_date"), end_date: data.get("end_date"), notes: data.get("notes"),
            season_type: seasonType, is_historical: isHistorical,
            fallow_reason: seasonType === "fallow" ? data.get("fallow_reason") : "",
            missing_period_reason: seasonType === "missing_period" ? data.get("missing_period_reason") : "",
          } });
          setSelected(row.id); form.reset(); setSeasonType("single_crop"); setIsHistorical(false);
          await queryClient.invalidateQueries({ queryKey: ["crop-seasons", field.field_id] });
          await queryClient.invalidateQueries({ queryKey: ["crop-corpus"] }); setNotice("Crop season saved.");
        });
      }}>
        <label className="text-sm">Season name<TextInput name="name" required maxLength={120} placeholder="Winter 2025–26" /></label>
        <label className="text-sm">Season type
          <Select value={seasonType} onChange={e => setSeasonType(e.target.value)}>
            <option value="single_crop">Single crop</option>
            <option value="rotation">Rotation (multiple crops in sequence)</option>
            <option value="intercrop">Intercrop (crops grown together)</option>
            <option value="cover_crop">Cover crop</option>
            <option value="fallow">Fallow (documented, no crop)</option>
            <option value="missing_period">Missing period (records unavailable)</option>
          </Select>
        </label>
        {seasonType !== "fallow" && seasonType !== "missing_period" && (
          <label className="text-sm">Crops, separated by commas<TextInput name="crops" required placeholder="Wheat, lentil" /></label>
        )}
        <label className="text-sm">Start date<TextInput name="start_date" type="date" required /></label>
        <label className="text-sm">End date (inclusive)<TextInput name="end_date" type="date" required /></label>
        {seasonType === "fallow" && (
          <label className="text-sm sm:col-span-2">Fallow reason (required)<TextInput name="fallow_reason" required maxLength={500} placeholder="e.g. field rested between rice seasons" /></label>
        )}
        {seasonType === "missing_period" && (
          <label className="text-sm sm:col-span-2">Why records are unavailable (required)<TextInput name="missing_period_reason" required maxLength={500} placeholder="e.g. farmer records lost for this year" /></label>
        )}
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={isHistorical} onChange={e => setIsHistorical(e.target.checked)} />
          This is historical/baseline evidence (predates the monitored project period), not a monitored project-period season.
        </label>
        <label className="text-sm sm:col-span-2">Notes<TextInput name="notes" maxLength={2000} /></label>
        <p className="text-xs text-text-tertiary sm:col-span-2">
          Rotation/intercrop crop-sequence sub-periods and grouped-project eligibility areas are not yet editable here — see the
          field&apos;s Quantification Units tab and the API for the fuller data model.
        </p>
        <div><Button loading={busy} type="submit">Save season</Button></div>
      </form>
    </Card>}
    {seasons.isLoading ? <p role="status">Loading seasons…</p> : !seasons.data?.length ? <Card>No crop seasons recorded yet.</Card> : <>
      <label className="block text-sm font-medium">Selected season<Select value={seasonId} onChange={e => setSelected(e.target.value)}>
        {seasons.data.map(s => <option key={s.id} value={s.id}>{s.payload.name} · {s.payload.crops.join(" + ")} · {s.payload.start_date} to {s.payload.end_date}</option>)}
      </Select></label>
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-medium">Satellite observations</h3>
          {writable && <Button variant="secondary" loading={busy || running} onClick={() => void perform(async () => {
            const accepted = await apiFetch<{ job_id: string }>(`${path}/monitoring-runs`, { method: "POST" }); setJobId(accepted.job_id);
          })}>Collect completed-season observations</Button>}
        </div>
        <p className="mt-2 text-sm text-text-secondary">Sentinel-1 radar and Sentinel-2 vegetation, moisture, and residue-related indices. Coverage checks are exploratory and do not verify a crop or practice.</p>
        {running && <p role="status" className="mt-3 text-sm">Processing… This may take a few minutes.</p>}
        {latest ? <div className="mt-3 space-y-2 text-sm">
          <p>{latest.payload.quality.status === "insufficient_evidence" ? "Insufficient observation coverage" : "Ready for exploration"} · {latest.payload.processing_version}</p>
          {Object.entries(latest.payload.quality.sensors).map(([sensor, q]) => <p key={sensor}>{sensor}: {q.usable_dates} usable dates · longest gap {q.max_gap_days} days</p>)}
          {latest.payload.quality.warnings.map(w => <p key={w} className="text-warning-700">{w}</p>)}
        </div> : <p className="mt-3 text-sm text-text-tertiary">No saved satellite snapshot for this season.</p>}
        {evidence.data && <Button className="mt-3" variant="ghost" onClick={() => download(evidence.data, `evidence-${seasonId}.json`)}>Download evidence with source records</Button>}
      </Card>
      {writable && <Card>
        <h3 className="mb-3 font-medium">Record a field observation</h3>
        <form key={seasonId} className="grid gap-3 sm:grid-cols-2" onSubmit={e => {
          e.preventDefault(); const form = e.currentTarget; const data = new FormData(form);
          void perform(async () => {
            await apiFetch(`${path}/observations`, { method: "POST", json: {
              kind, source: data.get("source"), observed_at: new Date(String(data.get("observed_at"))).toISOString(),
              value: data.get("value"), numeric_value: numeric ? Number(data.get("numeric_value")) : null,
              evidence_reference: data.get("evidence_reference"), notes: data.get("notes"),
            } }); form.reset(); await evidence.refetch(); setNotice("Observation saved for another team member to review.");
          });
        }}>
          <label className="text-sm">Observation type<Select value={kind} onChange={e => setKind(e.target.value)}>
            {[["crop_identity", "Crop identity"], ["water_level", "Water level"], ["irrigation", "Irrigation"], ["planting", "Planting"], ["harvest", "Harvest"], ["residue_cover", "Residue cover"], ["practice", "Management practice"]].map(([v, t]) => <option value={v} key={v}>{t}</option>)}
          </Select></label>
          <label className="text-sm">Source<Select name="source">
            <option value="field_measurement">Field measurement</option><option value="expert_observation">Expert observation</option><option value="farmer_report">Farmer report</option><option value="document">Document</option>
          </Select></label>
          <label className="text-sm">Observed at (your local time)<TextInput name="observed_at" type="datetime-local" required /></label>
          <label className="text-sm">{kind === "crop_identity" ? "Observed crop name" : "Observation description"}<TextInput name="value" required maxLength={500} /></label>
          {numeric && <label className="text-sm">{kind === "water_level" ? "Water level, cm (negative below soil surface)" : "Residue cover, %"}<TextInput name="numeric_value" type="number" step="any" required min={kind === "residue_cover" ? 0 : undefined} max={kind === "residue_cover" ? 100 : undefined} /></label>}
          <label className="text-sm">Evidence reference<TextInput name="evidence_reference" required maxLength={1000} placeholder="Survey record ID, photo reference, or document page" /></label>
          <label className="text-sm">Notes<TextInput name="notes" maxLength={2000} /></label>
          <p className="text-xs text-text-secondary sm:col-span-2">Only crop identities from field measurements or expert observations, accepted by a different team member, enter the benchmark. Evidence files remain in your existing storage; record their reference here.</p>
          <div><Button type="submit" loading={busy}>Save observation</Button></div>
        </form>
      </Card>}
      <Card>
        <h3 className="mb-3 font-medium">Evidence review</h3>
        {evidence.isLoading ? <p>Loading evidence…</p> : !evidence.data?.observations.length ? <p className="text-sm text-text-secondary">No field observations yet.</p> : evidence.data.observations.map(o => {
          const reviews = evidence.data!.reviews.filter(r => r.payload.observation_id === o.id);
          const review = reviews.at(-1);
          return <div key={o.id} className="border-t border-border py-4 text-sm">
            <p className="font-medium">{o.payload.value}{o.payload.numeric_value !== null ? ` · ${o.payload.numeric_value} ${o.payload.kind === "water_level" ? "cm" : "%"}` : ""}</p>
            <p className="text-text-secondary">{o.payload.source.replaceAll("_", " ")} · {new Date(o.payload.observed_at).toLocaleString()} · {review?.payload.decision ?? "Awaiting review"}</p>
            <p className="break-words text-text-secondary">Evidence: {o.payload.evidence_reference}</p>
            {review && <p>Review: {review.payload.reason}</p>}
            {reviews.length > 1 && <details className="mt-2"><summary>Review history ({reviews.length})</summary>{reviews.map(r => <p key={r.id}>{r.payload.decision}: {r.payload.reason}</p>)}</details>}
            {writable && o.payload.created_by !== session?.user_id && <form className="mt-3 flex flex-wrap gap-2" onSubmit={e => {
              e.preventDefault(); const data = new FormData(e.currentTarget);
              void perform(async () => {
                await apiFetch(`${path}/observations/${o.id}/reviews`, { method: "POST", json: { decision: data.get("decision"), reason: data.get("reason") } });
                await evidence.refetch(); await corpus.refetch(); setNotice("Review saved.");
              });
            }}>
              <Select name="decision" aria-label="Review decision" className="max-w-40"><option value="accepted">Accept</option><option value="rejected">Reject</option></Select>
              <TextInput name="reason" aria-label="Reason for review" placeholder="Reason and evidence checked" required maxLength={2000} className="max-w-md" />
              <Button type="submit" variant="secondary" loading={busy}>Save review</Button>
            </form>}
          </div>;
        })}
      </Card>
    </>}
    <Card>
      <h3 className="font-medium">Multi-crop benchmark · your organization</h3>
      <p className="mt-2 text-sm text-text-secondary">Compare Random Forest and XGBoost on reviewed single-crop seasons across your fields. Mixed crops remain in your records but need a separate multi-label model. Models are evaluated here, not deployed.</p>
      <p className="mt-3 text-sm">{corpus.data?.examples.length ?? 0} eligible seasons · {corpus.data?.excluded.length ?? 0} excluded seasons</p>
      {!!corpus.data?.excluded.length && <details className="mt-2 text-sm"><summary>Why seasons are excluded</summary><ul className="mt-2 list-disc pl-5">{corpus.data.excluded.map(r => <li key={r.season_id}>{seasons.data?.find(s => s.id === r.season_id)?.payload.name ?? r.season_id}: {r.reason}</li>)}</ul></details>}
      <div className="mt-3 flex flex-wrap gap-3">
        <Select aria-label="Benchmark split" className="max-w-xs" value={split} onChange={e => setSplit(e.target.value)}><option value="field">Hold out fields</option><option value="year">Hold out years and exclude shared fields</option><option value="district">Hold out districts</option></Select>
        {writable && <Button disabled={(corpus.data?.examples.length ?? 0) < 4} loading={busy || running} onClick={() => void perform(async () => {
          const accepted = await apiFetch<{ job_id: string }>("/multi-crop/benchmarks", { method: "POST", json: { split, models: ["random_forest", "xgboost"] } }); setJobId(accepted.job_id);
        })}>Run comparison</Button>}
        {corpus.data && <Button variant="ghost" onClick={() => download(corpus.data, "crop-benchmark-dataset.json")}>Export benchmark dataset</Button>}
      </div>
      <p className="mt-2 text-xs text-text-tertiary">Needs at least four eligible seasons, two crops, and enough independent groups to represent each held-out crop in training. WorldCereal/Presto remains a follow-up experiment.</p>
      {!!history.data?.length && <label className="mt-3 block text-sm">Saved comparisons<Select value={history.data.some(h => h.job_id === jobId) ? jobId! : ""} onChange={e => { if (e.target.value) setJobId(e.target.value); }} disabled={running}>
        <option value="">Choose a completed comparison</option>
        {history.data.map((h, i) => <option value={h.job_id} key={h.job_id}>{i === 0 ? "Latest" : `Run ${history.data.length - i}`} · hold out {h.split} · dataset {h.dataset_sha256.slice(0, 8)}</option>)}
      </Select></label>}
      {result && <div className="mt-4 space-y-2 text-sm">
        {Object.entries(result.models).map(([name, metrics]) => <p key={name}>{name}: macro F1 {metrics.report["macro avg"].f1.toFixed(3)} · log loss {metrics.log_loss.toFixed(3)} · Brier score {metrics.brier_score.toFixed(3)}</p>)}
        <p>Research results only. Probabilities are not calibrated.</p>
        <Button variant="secondary" onClick={() => download(job.data?.result, "crop-benchmark-results.json")}>Download results and frozen dataset</Button>
      </div>}
    </Card>
  </div>;
}
