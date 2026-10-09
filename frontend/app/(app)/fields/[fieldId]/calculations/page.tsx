"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, CheckCircle2, Save, Satellite, Sprout, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { useSession } from "@/app/providers";
import { ExplainButton } from "@/components/ai/ExplainDrawer";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card, StatCard } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Select, TextInput } from "@/components/ui/Field";
import { useCalculationHistory, useCommitCalculation, usePreviewCalculation, useRecordDetermination } from "@/hooks/use-calculations";
import { useCropSeasons } from "@/hooks/use-crop-seasons";
import { useProjectMembers, useProjects } from "@/hooks/use-projects";
import { useCreateSubmission } from "@/hooks/use-reviews";
import { apiFetch, apiFetchBlob } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { formatDate, formatNumber, formatQueueTimestamp } from "@/lib/format";
import { AMENDMENT_TYPE_OPTIONS } from "@/lib/schemas/ledger";
import type { AccountingPathway, CalculationHistoryRow, ReadinessCheck } from "@/types/api";

const PATHWAY_BY_FIELD_TYPE: Record<string, AccountingPathway> = {
  rice_awd: "vm0051_rice_awd",
  cropland_alm_vm0042: "vm0042_alm",
};
const STATUS_TONE: Record<string, "brand" | "success" | "warning" | "neutral"> = {
  draft: "warning", ready_for_review: "success", superseded: "neutral",
};
const READINESS_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  satisfied: "success", not_applicable: "neutral", unsupported: "neutral", missing: "danger", needs_review: "warning",
};
// Which field tab fixes a blocking readiness item.
const FIX_TAB: Record<string, string> = {
  "common.monitoring_period_coverage": "crop-seasons", "common.evidence_review_status": "crop-seasons",
  "vm0042.historical_lookback": "crop-seasons", "vm0042.rotation_completeness": "crop-seasons",
  "common.methodology_applicability": "enrollment", "common.additionality": "enrollment",
  "vm0051.required_measurement_inputs": "signal-analytics",
  "vm0042.project_practice_schedule": "practice-data", "vm0042.baseline_documentation": "practice-data",
  "vm0042.soc_measurements": "practice-data", "vm0042.soc_sampling_traceability": "soil-evidence",
  "vm0042.soc_uncertainty_annualization": "soil-evidence",
  "vm0042.leakage_evidence_review": "production-records", "vm0042.other_leakage_scope": "production-records",
};
const isBlocking = (c: ReadinessCheck) => ["missing", "needs_review", "unsupported"].includes(c.status) && (c as { blocking?: boolean }).blocking !== false;

type Run = { job_id: string; window_start: string; window_end: string; total_awd: number; season_length_days: number };

// The last calculation request per field, for this browser tab. Coming back
// to the page re-runs it (preview never writes), so the result and the things
// to fix reappear — re-checked, so items fixed in the meantime drop off.
type LastCalculation = { runChoice: string; manual: boolean; body: Record<string, unknown> };
const lastCalculationKey = (fieldId: string) => `terra-audit:last-calculation:${fieldId}`;
function loadLastCalculation(fieldId: string): LastCalculation | null {
  try {
    const raw = window.sessionStorage.getItem(lastCalculationKey(fieldId));
    return raw ? JSON.parse(raw) as LastCalculation : null;
  } catch { return null; }
}
function storeLastCalculation(fieldId: string, value: LastCalculation) {
  try { window.sessionStorage.setItem(lastCalculationKey(fieldId), JSON.stringify(value)); } catch { /* storage unavailable */ }
}

function download(value: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const a = document.createElement("a"); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url);
}

function ReadinessList({ checklist, explain, highlighted }: { checklist: ReadinessCheck[]; explain?: (id: string) => React.ReactNode; highlighted?: string }) {
  return (
    <div className="space-y-2">
      {checklist.map((c) => (
        <div key={c.requirement_id} className={`flex flex-wrap items-start gap-2 border-t border-border py-2 text-sm first:border-t-0 first:pt-0 ${c.requirement_id === highlighted ? "rounded-lg bg-brand-50 px-3" : ""}`}>
          <Badge tone={READINESS_TONE[c.status]}>{c.status.replace("_", " ")}</Badge>
          {explain && isBlocking(c) && explain(c.requirement_id)}
          <div className="min-w-0 flex-1">
            <p className="font-mono text-xs text-text-tertiary">{c.requirement_id}</p>
            <p>{c.explanation}</p>
            {c.decided_by && <p className="text-xs text-text-secondary">Recorded decision: {c.reason}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function CalculationsPage() {
  const field = useFieldContext();
  const search = useSearchParams();
  return <CalculationsView key={`${field.field_id}:${search.toString()}`} />;
}

/** One form, one Calculate click, a clear result, then Save. Dates, crop
 * seasons, AWD values and the project are filled in from saved data (the
 * latest rule-based Signal Analytics run and the field's project). Readiness
 * still runs on every calculation, but only items that block are shown;
 * the full checklist, manual dates, corrections and evidence reviews live
 * under Advanced. */
function CalculationsView() {
  const field = useFieldContext();
  const search = useSearchParams();
  const session = useSession();
  const queryClient = useQueryClient();
  const writable = session?.role === "admin" || session?.role === "analyst";
  const pathway = PATHWAY_BY_FIELD_TYPE[field.field_type];
  const isRice = pathway === "vm0051_rice_awd";
  const base = `/fields/${encodeURIComponent(field.field_id)}`;
  const highlighted = search.get("requirement") ?? "";
  const urlDate = (key: string) => /^\d{4}-\d{2}-\d{2}$/.test(search.get(key) ?? "") ? search.get(key)! : "";

  const seasons = useCropSeasons(field.field_id);
  const runs = useQuery({
    queryKey: ["signal-evidence", field.field_id],
    queryFn: () => apiFetch<Run[]>(`${base}/signal-runs/evidence`),
    enabled: isRice,
  });
  const history = useCalculationHistory(field.field_id);
  const preview = usePreviewCalculation(field.field_id);
  const commit = useCommitCalculation(field.field_id);
  const determination = useRecordDetermination(field.field_id);
  const createSubmission = useCreateSubmission();
  const projects = useProjects();

  // Manual context (Advanced) — also used for deep links that carry dates.
  // A deep link wins over the remembered calculation.
  const deepLink = !!urlDate("start") && !!urlDate("end");
  const [last, setLast] = useState(() => deepLink ? null : loadLastCalculation(field.field_id));
  const restoring = last?.manual ? last.body : null;
  const [manual, setManual] = useState(() => deepLink || !!last?.manual);
  const [periodStart, setPeriodStart] = useState(() => urlDate("start") || String(restoring?.monitoring_period_start ?? ""));
  const [periodEnd, setPeriodEnd] = useState(() => urlDate("end") || String(restoring?.monitoring_period_end ?? ""));
  const [manualSeasons, setManualSeasons] = useState<string[]>(() => (restoring?.season_ids as string[] | undefined) ?? search.getAll("season"));
  const [runChoice, setRunChoice] = useState(() => last?.runChoice ?? "");
  const [projectId, setProjectId] = useState(() => search.get("project")
    ?? (last ? (last.body.project_id as string | null) ?? "" : field.current_project?.project_id ?? ""));
  const [supersedes, setSupersedes] = useState("");
  const [dirty, setDirty] = useState(true);
  const [lastBody, setLastBody] = useState<Record<string, unknown> | null>(null);
  const [saved, setSaved] = useState<{ id: string; status: string; version: number; projectId: string | null } | null>(null);
  const toast = useToast();

  const members = useProjectMembers(projectId || undefined);
  const canReview = session?.role === "admin" || (session?.role === "analyst" &&
    members.data?.some((m) => m.user_id === session.user_id && m.project_role === "lead"));

  // Automatic context: the chosen (default: latest) saved run's exact window
  // and the crop seasons overlapping it; cropland uses its latest season.
  const allSeasons = seasons.data ?? [];
  const run = isRice ? (runs.data?.find((r) => r.job_id === runChoice) ?? runs.data?.[0]) : undefined;
  const latestSeason = [...allSeasons].sort((a, b) => b.payload.end_date.localeCompare(a.payload.end_date))[0];
  const auto = isRice
    ? run && { start: run.window_start, end: run.window_end,
      seasons: allSeasons.filter((s) => s.payload.start_date <= run.window_end && s.payload.end_date >= run.window_start).map((s) => s.id) }
    : latestSeason && { start: latestSeason.payload.start_date, end: latestSeason.payload.end_date, seasons: [latestSeason.id] };
  const context = manual ? { start: periodStart, end: periodEnd, seasons: manualSeasons } : auto;
  // A saved run is only used as evidence when its window matches exactly.
  const evidenceRun = isRice ? (runs.data ?? []).find((r) => r.window_start === context?.start && r.window_end === context?.end) : undefined;
  const project = projects.data?.find((p) => p.project_id === projectId);

  const contextIssue = !pathway ? "This field has no supported calculation pathway." :
    !context ? "" :
    !context.seasons.length ? "No crop season covers this period — add one in Crop Seasons or adjust the dates under Advanced." :
    !context.start || !context.end ? "Set both monitoring dates under Advanced." :
    context.end < context.start ? "The period end must be on or after its start." : "";
  const busy = preview.isPending || commit.isPending || determination.isPending || createSubmission.isPending;
  const result = !dirty ? preview.data : undefined;
  const blocking = result ? result.readiness.filter(isBlocking) : [];
  const openCalculations = (history.data ?? []).filter((r) => !r.legacy && r.status !== "superseded");
  // The remembered request applies only while the page still shows the same context.
  const lastMatches = !!last && !!context && !contextIssue && last.body.monitoring_period_start === context.start
    && last.body.monitoring_period_end === context.end && JSON.stringify(last.body.season_ids) === JSON.stringify(context.seasons);
  const lastInputs = lastMatches ? last!.body.engine_inputs as Record<string, unknown> : undefined;
  const lastAmendment = (lastInputs?.project_amendments as [string, number][] | undefined)?.[0];

  const runPreview = preview.mutateAsync;
  const contextReady = !!context && seasons.isSuccess;
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current || !contextReady) return;
    restored.current = true;
    if (!writable || !lastMatches) return;
    const body = { ...last!.body, signal_run_id: evidenceRun?.job_id ?? null };
    runPreview(body).then(() => { setLastBody(body); setDirty(false); })
      .catch(() => { /* inputs no longer valid — the user recalculates */ });
  }, [contextReady, writable, lastMatches, last, evidenceRun, runPreview]);

  function markDirty() { setDirty(true); setSaved(null); }

  async function perform(title: string, action: () => Promise<void>) {
    try {
      await action();
    } catch (e) {
      // The membership-period error has a direct fix: correct the join date.
      const membership = e instanceof Error && e.message.includes("not a member of the selected project") && projectId;
      toast.error(e, title, membership ? { label: "Change start date", href: `/projects/${encodeURIComponent(projectId)}/fields` } : undefined);
    }
  }

  function readInputs(form: HTMLFormElement): Record<string, unknown> {
    const data = new FormData(form);
    const number = (name: string, label: string) => {
      const value = data.get(name);
      if (typeof value !== "string" || !value.trim() || !Number.isFinite(Number(value))) throw new Error(`Enter a value for ${label}.`);
      return Number(value);
    };
    if (isRice) {
      const amendment = [data.get("amendment_type"), number("amendment_rate", "amendment rate")];
      return {
        awd_events: number("awd_events", "AWD events"), season_length_days: number("season_length_days", "season length"),
        q_n_kg_per_ha: number("q_n_kg_per_ha", "nitrogen input"), preseason_category: data.get("preseason_category"),
        baseline_amendments: [amendment], project_amendments: [amendment],
      };
    }
    return { verification_years: number("verification_years", "verification years"),
      non_permanence_risk_pct: number("non_permanence_risk_pct", "non-permanence risk") };
  }

  const explain = (id: string) => projectId && context ? (
    <ExplainButton projectId={projectId} request={{ action: "missing_evidence", field_id: field.field_id, requirement_id: id,
      monitoring_period_start: context.start, monitoring_period_end: context.end, season_ids: context.seasons }}>Explain</ExplainButton>
  ) : null;

  // ---- prerequisites -------------------------------------------------------
  if (seasons.isLoading || (isRice && runs.isLoading)) return <div className="ui-container"><p role="status">Loading…</p></div>;
  if (!allSeasons.length) {
    return <div className="ui-container"><EmptyState icon={Sprout} title="Add a crop season first" description="A calculation covers one or more crop seasons."
      action={<ButtonLink href={`${base}/crop-seasons`}>Go to Crop Seasons</ButtonLink>} /></div>;
  }
  if (isRice && !runs.data?.length && !manual) {
    return <div className="ui-container"><EmptyState icon={Satellite} title="Run Signal Analytics first" description="The calculation uses the AWD events and season length from a saved satellite analysis."
      action={<ButtonLink href={`${base}/signal-analytics`}>Go to Signal Analytics</ButtonLink>} /></div>;
  }

  return (
    <div className="ui-container space-y-6">
      <h2 className="ui-section-title">Calculations</h2>

      {writable && <Card>
        <div className="mb-4 space-y-1 text-sm">
          {isRice && !manual && (
            <label className="block">Based on
              <Select value={run?.job_id ?? ""} disabled={busy} onChange={(e) => { setRunChoice(e.target.value); markDirty(); }}>
                {(runs.data ?? []).map((r) => (
                  <option key={r.job_id} value={r.job_id}>Signal Analytics · {formatDate(r.window_start)} – {formatDate(r.window_end)} · {r.total_awd} AWD events</option>
                ))}
              </Select>
            </label>
          )}
          {context && (
            <p className="text-text-secondary">
              Period {formatDate(context.start)} – {formatDate(context.end)} ·{" "}
              {context.seasons.map((id) => allSeasons.find((s) => s.id === id)?.payload.name).filter(Boolean).join(", ") || "no crop season"} ·{" "}
              {project ? `Project: ${project.name}` : "Standalone (preliminary)"} · {field.area_ha?.toFixed(2)} ha
            </p>
          )}
          {contextIssue && <p role="status" className="text-warning-700">{contextIssue}</p>}
        </div>

        <form key={`${run?.job_id}:${manual}`} className="grid gap-3 sm:grid-cols-2" onChange={markDirty} onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          void perform("Couldn't calculate", async () => {
            if (!context || contextIssue) throw new Error(contextIssue || "Choose a period first.");
            const body = { project_id: projectId || null, accounting_pathway: pathway, season_ids: context.seasons,
              monitoring_period_start: context.start, monitoring_period_end: context.end,
              engine_inputs: readInputs(form), signal_run_id: evidenceRun?.job_id ?? null };
            await preview.mutateAsync(body);
            setLastBody(body); setDirty(false); setSaved(null);
            const remembered = { runChoice: manual ? "" : run?.job_id ?? "", manual, body };
            storeLastCalculation(field.field_id, remembered); setLast(remembered);
          });
        }}>
          {isRice ? (
            <>
              <label className="text-sm">AWD events<TextInput name="awd_events" type="number" min={0} required defaultValue={String(lastInputs?.awd_events ?? evidenceRun?.total_awd ?? "")} /></label>
              <label className="text-sm">Season length (days)<TextInput name="season_length_days" type="number" min={1} required defaultValue={String(lastInputs?.season_length_days ?? evidenceRun?.season_length_days ?? "")} /></label>
              <label className="text-sm">Pre-season water regime<Select name="preseason_category" defaultValue={String(lastInputs?.preseason_category ?? "short")}>
                <option value="short">Non-flooded &lt; 180 days (double/multi-cropping)</option><option value="long">Non-flooded &gt; 180 days (single cropping)</option>
              </Select></label>
              <label className="text-sm">N input (kg N/ha)<TextInput name="q_n_kg_per_ha" type="number" step="any" min={0} required defaultValue={Number(lastInputs?.q_n_kg_per_ha ?? 100)} /></label>
              <label className="text-sm">Organic amendment<Select name="amendment_type" defaultValue={lastAmendment?.[0] ?? "straw_shortly_before"}>
                {AMENDMENT_TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select></label>
              <label className="text-sm">Application rate (t/ha)<TextInput name="amendment_rate" type="number" step="any" min={0} required defaultValue={lastAmendment?.[1] ?? 5} /></label>
            </>
          ) : (
            <>
              <label className="text-sm">Verification years<TextInput name="verification_years" type="number" step="any" min={1} required defaultValue={Number(lastInputs?.verification_years ?? 1)} /></label>
              <label className="text-sm">Non-permanence risk (%)<TextInput name="non_permanence_risk_pct" type="number" step="any" min={0} max={100} required defaultValue={Number(lastInputs?.non_permanence_risk_pct ?? 20)} /></label>
            </>
          )}
          <div className="sm:col-span-2">
            <Button type="submit" icon={Calculator} loading={preview.isPending} disabled={busy || !context || !!contextIssue}>Calculate</Button>
          </div>
        </form>
      </Card>}

      {result && (
        <Card className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard label="Estimated reductions (tCO2e)" value={formatNumber(result.result.final_issuance as number | null, "tco2e")} tone="success" />
            {isRice && <StatCard label="Baseline CH4 (tCO2e)" value={formatNumber(result.result.e_baseline as number | null, "tco2e")} />}
            {isRice && <StatCard label="Project CH4 (tCO2e)" value={formatNumber(result.result.e_project as number | null, "tco2e")} />}
          </div>
          {!!result.result.leakage_block_reason && <p className="text-sm text-danger-700">{String(result.result.leakage_block_reason)}</p>}
          <p className="ui-meta">Calculated estimate — not issued credits.</p>

          {blocking.length ? (
            <div className="rounded-lg border border-warning-600/25 bg-warning-50/60 p-3 text-sm">
              <p className="flex items-center gap-2 font-medium text-warning-700"><TriangleAlert className="size-4" />{blocking.length} thing{blocking.length > 1 ? "s" : ""} to fix before it can go to review</p>
              <ul className="mt-2 space-y-1.5">
                {blocking.map((c) => (
                  <li key={c.requirement_id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>{c.explanation}</span>
                    {FIX_TAB[c.requirement_id] && <Link className="font-medium underline" href={`${base}/${FIX_TAB[c.requirement_id]}`}>Fix</Link>}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="flex items-center gap-2 text-sm font-medium text-success-700"><CheckCircle2 className="size-4" />Ready to save{projectId ? " and submit for review" : ""}.</p>
          )}

          <div className="flex flex-wrap items-center gap-2">
            {!saved && <Button icon={Save} loading={commit.isPending} disabled={busy || !lastBody} onClick={() => void perform("Couldn't save calculation", async () => {
              const out = await commit.mutateAsync({ body: { ...lastBody, monitoring_run_ids: [], attachment_ids: [],
                supersedes_calculation_id: supersedes || null }, idempotencyKey: crypto.randomUUID() });
              setSaved({ id: out.calculation.calculation_id, status: out.calculation.status, version: out.calculation.version,
                projectId: (lastBody?.project_id as string | null) ?? null });
              toast.success("Calculation saved", { description: out.calculation.status === "ready_for_review"
                ? `Version ${out.calculation.version} · ready for review` : `Version ${out.calculation.version} · draft — fix the listed items before review` });
              await queryClient.invalidateQueries({ queryKey: ["calculations", field.field_id] });
              await queryClient.invalidateQueries({ queryKey: ["field-workflow", field.field_id] });
            })}>Save calculation</Button>}
            {saved?.status === "ready_for_review" && saved.projectId && (
              <Button variant="secondary" loading={createSubmission.isPending} onClick={() => void perform("Couldn't submit for review", async () => {
                const sub = await createSubmission.mutateAsync({ project_id: saved.projectId!, calculation_id: saved.id });
                toast.success("Submitted for review", { action: { label: "Open review", href: `/reviews/${encodeURIComponent(sub.submission_id)}` } });
                await queryClient.invalidateQueries({ queryKey: ["field-workflow", field.field_id] });
              })}>Submit for review</Button>
            )}
            {saved && !saved.projectId && <span className="ui-meta">Standalone calculation — add the field to a project to submit it for review.</span>}
          </div>
        </Card>
      )}

      <details className="ui-card" open={!!highlighted || manual}>
        <summary className="ui-subsection-title cursor-pointer">Advanced</summary>
        <div className="mt-4 space-y-5 text-sm">
          <section className="space-y-2">
            <label className="flex items-center gap-2"><input type="checkbox" checked={manual} disabled={busy} onChange={(e) => {
              if (e.target.checked && auto) { setPeriodStart(auto.start); setPeriodEnd(auto.end); setManualSeasons(auto.seasons); }
              setManual(e.target.checked); markDirty();
            }} />Choose dates and crop seasons manually</label>
            {manual && <>
              <div className="flex flex-wrap gap-2">
                {allSeasons.map((s) => (
                  <label key={s.id} className={`cursor-pointer rounded-lg border px-3 py-1.5 ${manualSeasons.includes(s.id) ? "border-brand-600 bg-brand-50 text-brand-700" : "border-border"}`}>
                    <input type="checkbox" className="mr-1.5" checked={manualSeasons.includes(s.id)} onChange={() => {
                      setManualSeasons((ids) => ids.includes(s.id) ? ids.filter((x) => x !== s.id) : [...ids, s.id]); markDirty();
                    }} />
                    {s.payload.name} · {formatDate(s.payload.start_date)} – {formatDate(s.payload.end_date)}
                  </label>
                ))}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <label>Period start<TextInput type="date" value={periodStart} onChange={(e) => { setPeriodStart(e.target.value); markDirty(); }} /></label>
                <label>Period end<TextInput type="date" value={periodEnd} onChange={(e) => { setPeriodEnd(e.target.value); markDirty(); }} /></label>
              </div>
            </>}
          </section>
          <label className="block">Project
            <Select value={projectId} disabled={busy} onChange={(e) => { setProjectId(e.target.value); markDirty(); }}>
              <option value="">No project (preliminary)</option>
              {(projects.data ?? []).map((p) => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
            </Select>
          </label>
          {!!openCalculations.length && (
            <label className="block">Correct an existing calculation
              <Select value={supersedes} disabled={busy} onChange={(e) => setSupersedes(e.target.value)}>
                <option value="">No — save as a new calculation</option>
                {openCalculations.map((c) => "calculation_id" in c && c.calculation_id && (
                  <option key={c.calculation_id} value={c.calculation_id}>v{c.version} · {c.status.replace("_", " ")} · {formatQueueTimestamp(c.created_at)}</option>
                ))}
              </Select>
            </label>
          )}
          {result && (
            <section>
              <p className="mb-2 font-medium">Full readiness checklist</p>
              <ReadinessList checklist={result.readiness} explain={explain} highlighted={highlighted} />
            </section>
          )}
          {canReview && projectId && result && context && (
            <form className="space-y-2" onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              void perform("Couldn't save review", async () => {
                await determination.mutateAsync({ project_id: projectId, accounting_pathway: pathway, season_ids: context.seasons,
                  monitoring_period_start: context.start, monitoring_period_end: context.end,
                  requirement_id: String(data.get("requirement")), status: String(data.get("decision")), reason: String(data.get("reason")) });
                preview.reset(); markDirty();
                toast.success("Review saved", { description: "Click Calculate again to update the result." });
              });
            }}>
              <p className="font-medium">Record an evidence review</p>
              <Select aria-label="Requirement to review" name="requirement" required defaultValue={result.readiness.some((c) => c.requirement_id === highlighted) ? highlighted : ""}>
                <option value="">Select a requirement</option>
                {result.readiness.filter((c) => c.reviewer_authority !== "automated_only" && c.implementation_support !== "unsupported")
                  .map((c) => <option key={c.requirement_id} value={c.requirement_id}>{c.requirement_id}</option>)}
              </Select>
              <Select aria-label="Review decision" name="decision" defaultValue="satisfied"><option value="satisfied">Evidence accepted</option><option value="not_applicable">Not applicable (where permitted)</option><option value="needs_review">Further review needed</option></Select>
              <TextInput aria-label="Review justification" name="reason" required placeholder="Decision, sources and justification" />
              <Button type="submit" variant="secondary" loading={determination.isPending}>Record review</Button>
            </form>
          )}
        </div>
      </details>

      <details className="ui-card">
        <summary className="ui-subsection-title cursor-pointer">History ({(history.data ?? []).length})</summary>
        {history.isLoading ? <p className="mt-2 text-sm">Loading…</p> : history.isError ? <p role="alert">Unable to load history: {history.error.message}</p> : !history.data?.length ? (
          <p className="mt-2 text-sm text-text-secondary">No calculations yet.</p>
        ) : (
          <div className="mt-3 space-y-2">
            {history.data.map((row: CalculationHistoryRow) => (
              <div key={row.legacy ? `legacy-${row.credit_history_id}` : row.calculation_id} className="flex flex-wrap items-center justify-between gap-2 border-t border-border py-2 text-sm first:border-t-0 first:pt-0">
                <div>
                  {row.legacy ? <Badge tone="neutral">legacy</Badge> : <>
                    <Badge tone={STATUS_TONE[row.status]}>{row.status.replace("_", " ")}</Badge>{" "}
                    <span className="font-mono text-xs text-text-tertiary">v{row.version}</span>
                  </>}
                  <span className="ml-2">{formatQueueTimestamp(row.created_at)}</span>
                  <span className="ml-2 font-mono">{row.final_issuance == null ? "—" : formatNumber(row.final_issuance, "tco2e")} tCO2e</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {!row.legacy && row.status === "ready_for_review" && row.project_id && writable && (
                    <Button variant="secondary" size="sm" loading={createSubmission.isPending} onClick={() => void perform("Couldn't submit for review", async () => {
                      const sub = await createSubmission.mutateAsync({ project_id: row.project_id!, calculation_id: row.calculation_id! });
                      toast.success("Submitted for review", { action: { label: "Open review", href: `/reviews/${encodeURIComponent(sub.submission_id)}` } });
                    })}>Submit for review</Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => download(row, row.legacy ? `credit-history-${row.credit_history_id}.json` : `calculation-${row.calculation_id}.json`)}>JSON</Button>
                  {!row.legacy && pathway === "vm0042_alm" && <Button variant="ghost" size="sm" onClick={() => void perform("Download failed", async () => {
                    downloadBlob(await apiFetchBlob(`/calculations/${row.calculation_id}/evidence/pdf`), `calculation-${row.calculation_id}.pdf`);
                  })}>PDF</Button>}
                </div>
              </div>
            ))}
          </div>
        )}
      </details>
    </div>
  );
}
