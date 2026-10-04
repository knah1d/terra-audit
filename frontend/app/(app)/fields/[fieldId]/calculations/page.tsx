"use client";

import { useSearchParams } from "next/navigation";
import { AMENDMENT_TYPE_OPTIONS } from "@/lib/schemas/ledger";
import { formatDate, formatNumber, formatQueueTimestamp } from "@/lib/format";
import { useState } from "react";
import { ExplainButton } from "@/components/ai/ExplainDrawer";
import { useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/app/providers";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput } from "@/components/ui/Field";
import { apiFetch, apiFetchBlob } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import {
  useCalculationHistory, useCommitCalculation, usePreviewCalculation, useReadiness, useRecordDetermination,
} from "@/hooks/use-calculations";
import { useCropSeasons } from "@/hooks/use-crop-seasons";
import { useProjectMembers, useProjects } from "@/hooks/use-projects";
import { useCreateSubmission } from "@/hooks/use-reviews";
import type { AccountingPathway, CalculationHistoryRow, ReadinessCheck } from "@/types/api";
import Link from "next/link";


const PATHWAY_BY_FIELD_TYPE: Record<string, AccountingPathway> = {
  rice_awd: "vm0051_rice_awd",
  cropland_alm_vm0042: "vm0042_alm",
};

const STATUS_TONE: Record<string, "brand" | "success" | "warning" | "neutral"> = {
  draft: "warning", ready_for_review: "success", superseded: "neutral",
};

const READINESS_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  satisfied: "success", not_applicable: "neutral", unsupported: "neutral",
  missing: "danger", needs_review: "warning",
};

function download(value: unknown, name: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const a = document.createElement("a"); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url);
}

function ReadinessList({ checklist, explain, highlightedRequirement }: { checklist: ReadinessCheck[]; explain?: (id: string) => React.ReactNode; highlightedRequirement?: string }) {
  return (
    <div className="space-y-2">
      {checklist.map((c) => (
        <div key={c.requirement_id} className={`flex flex-wrap items-start gap-2 border-t border-border py-2 text-sm first:border-t-0 first:pt-0 ${c.requirement_id === highlightedRequirement ? "rounded-lg bg-brand-50 px-3" : ""}`}>
          <Badge tone={READINESS_TONE[c.status]}>{c.status.replace("_", " ")}</Badge>
          {explain && ["missing", "needs_review", "unsupported"].includes(c.status) && explain(c.requirement_id)}
          <div className="min-w-0 flex-1">
            <p className="font-mono text-xs text-text-tertiary">{c.requirement_id} {c.determination === "expert" && <span className="italic">· expert determination</span>}</p>
            <p>{c.explanation}</p>
            {c.source_reference && <p className="ui-meta">{c.source_reference}</p>}
            {c.required_evidence && <p className="ui-meta">Required evidence: {c.required_evidence}</p>}
            {c.implementation_support && c.implementation_support !== "implemented" && (
              <p className="text-xs text-warning-700">Implementation: {c.implementation_support === "unsupported" ? "not implemented by this system" : "partially implemented"}</p>
            )}
            {c.reviewer_authority === "automated_only" && <p className="ui-meta">Cannot be manually overridden.</p>}
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

function CalculationsView() {
  const field = useFieldContext();
  const search = useSearchParams();
  const requestedRequirement = search.get("requirement") ?? "";
  const requestedDate = (key: string) => /^\d{4}-\d{2}-\d{2}$/.test(search.get(key) ?? "") ? search.get(key)! : "";
  const session = useSession();
  const writable = session?.role === "admin" || session?.role === "analyst";
  const queryClient = useQueryClient();
  const pathway = PATHWAY_BY_FIELD_TYPE[field.field_type];

  const seasons = useCropSeasons(field.field_id);
  const history = useCalculationHistory(field.field_id);
  const readiness = useReadiness(field.field_id);
  const preview = usePreviewCalculation(field.field_id);
  const commit = useCommitCalculation(field.field_id);
  const determination = useRecordDetermination(field.field_id);
  const projects = useProjects();
  const createSubmission = useCreateSubmission();

  const [selectedSeasons, setSelectedSeasons] = useState<string[]>(() => search.getAll("season"));
  const [periodStart, setPeriodStart] = useState(() => requestedDate("start"));
  const [periodEnd, setPeriodEnd] = useState(() => requestedDate("end"));
  const [supersedes, setSupersedes] = useState("");
  const [projectId, setProjectId] = useState(() => search.get("project") ?? "");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const members = useProjectMembers(projectId || undefined);
  const canReview = session?.role === "admin" || (session?.role === "analyst" &&
    members.data?.some((member) => member.user_id === session.user_id && member.project_role === "lead"));
  const [readinessContext, setReadinessContext] = useState<string | null>(null);
  const [inputRevision, setInputRevision] = useState(0);
  const [previewContext, setPreviewContext] = useState<string | null>(null);
  const contextKey = JSON.stringify([field.field_id, pathway, projectId, periodStart, periodEnd,
    [...selectedSeasons].sort().map((id) => [id, seasons.data?.find((season) => season.id === id)?.version_record_id])]);
  const availableSeasons = seasons.data ?? [];
  const unavailableSeasons = selectedSeasons.filter((id) => !availableSeasons.some((season) => season.id === id));
  const contextIssue = !pathway ? "This field has no supported calculation pathway." :
    !selectedSeasons.length ? "Select at least one crop season." :
    !periodStart || !periodEnd ? "Set both monitoring dates." :
    periodEnd < periodStart ? "Monitoring period end must be on or after its start." :
    !seasons.data || unavailableSeasons.length > 0 ?
      "A selected crop season is unavailable. Select a current season below." :
    projectId && (!projects.data || !projects.data.some((project) => project.project_id === projectId)) ?
      "The selected project is unavailable. Choose an accessible project below." : "";
  const busy = preview.isPending || commit.isPending || determination.isPending || readiness.isPending;
  const currentReadiness = !contextIssue && readinessContext === contextKey && !readiness.isPending && !readiness.isError ? readiness.data : undefined;
  const previewKey = `${contextKey}:${inputRevision}`;
  const currentPreview = !contextIssue && previewContext === previewKey && !preview.isPending && !preview.isError ? preview.data : undefined;
  const reviewableRequirements = (currentPreview?.readiness ?? currentReadiness?.checklist ?? [])
    .filter((item) => item.reviewer_authority !== "automated_only" && item.implementation_support !== "unsupported");

  async function checkReadiness() {
    if (contextIssue) throw new Error(contextIssue);
    setReadinessContext(contextKey);
    await readiness.mutateAsync({ project_id: projectId || null, accounting_pathway: pathway, season_ids: selectedSeasons,
      monitoring_period_start: periodStart, monitoring_period_end: periodEnd });
  }

  const openCalculations = (history.data ?? []).filter((r) => !r.legacy && r.status !== "superseded");
  const legacyCount = (history.data ?? []).filter((r) => r.legacy).length;

  const explainRequirement = (id: string) => projectId && periodStart && periodEnd ? (
    <ExplainButton projectId={projectId} request={{ action: "missing_evidence", field_id: field.field_id,
      requirement_id: id, monitoring_period_start: periodStart, monitoring_period_end: periodEnd,
      season_ids: selectedSeasons }}>Explain</ExplainButton>
  ) : (
    <span className="inline-flex max-w-56 flex-col items-start gap-1">
      <Button variant="secondary" size="sm" disabled title={!projectId ? "Select a project to use AI explanations." : "Set both monitoring dates to use AI explanations."}>Explain</Button>
      <span className="text-xs text-text-secondary">{!projectId ? "Select a project to use AI explanations." : "Set both monitoring dates to use AI explanations."}</span>
    </span>
  );

  function toggleSeason(id: string) {
    setSelectedSeasons((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]));
  }

  function buildContext(engineInputs: Record<string, unknown>) {
    if (contextIssue) throw new Error(contextIssue);
    return {
      project_id: projectId || null,
      accounting_pathway: pathway,
      season_ids: selectedSeasons,
      monitoring_period_start: periodStart,
      monitoring_period_end: periodEnd,
      engine_inputs: engineInputs,
    };
  }

  async function perform(action: () => Promise<void>) {
    setError(""); setNotice("");
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Unable to complete this action"); }
  }

  function readEngineInputs(form: HTMLFormElement): Record<string, unknown> {
    const data = new FormData(form);
    function number(name: string) {
      const value = data.get(name);
      if (typeof value !== "string" || !value.trim() || !Number.isFinite(Number(value))) throw new Error(`Enter an evidence-backed value for ${name.replaceAll("_", " ")}.`);
      return Number(value);
    }
    if (pathway === "vm0051_rice_awd") {
      return {
        awd_events: number("awd_events"),
        season_length_days: number("season_length_days"),
        q_n_kg_per_ha: number("q_n_kg_per_ha"),
        preseason_category: data.get("preseason_category"),
        baseline_amendments: [[data.get("baseline_amendment_type"), number("baseline_amendment_rate")]],
        project_amendments: [[data.get("project_amendment_type"), number("project_amendment_rate")]],
      };
    }
    return {
      verification_years: number("verification_years"),
      non_permanence_risk_pct: number("non_permanence_risk_pct"),
    };
  }

  return (
    <div className="ui-container-wide space-y-6">
      <div>
        <h2 className="ui-section-title">Evidence-linked calculations</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Save a versioned calculation with its field boundary, crop seasons, practices and measurements frozen as evidence.
          Run readiness first, supply evidence-backed inputs, then prepare the calculation for internal review.
          Older ledger results remain available as legacy estimates; neither a saved result nor internal review is registry issuance.
        </p>
      </div>

      {requestedRequirement && <p role="status" className="ui-body">Review requested for <strong>{requestedRequirement}</strong>. Check the selected context, click Check readiness, then use Record an evidence review below. Only an authorized reviewer can record a decision.</p>}
      {error && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{error}</p>}
      {notice && <p role="status" className="text-sm text-success-700">{notice} <Link href={projectId ? `/reviews?project=${encodeURIComponent(projectId)}` : "/reviews"} className="underline">Go to Reviews</Link></p>}

      <Card>
        <h3 className="ui-subsection-title mb-3">Calculation context</h3>
        {seasons.isLoading ? <p role="status">Loading crop seasons…</p> : seasons.error ? <p role="alert">{seasons.error.message}</p> : !seasons.data?.length ? (
          <p className="ui-secondary">No crop seasons recorded yet — add one under Crop Seasons first.</p>
        ) : (
          <fieldset disabled={busy} className="space-y-3 text-sm">
            <div>
              <p className="mb-1.5 font-medium">Crop seasons in this accounting period</p>
              <div className="flex flex-wrap gap-2">
                {seasons.data.map((s) => (
                  <label key={s.id} className={`cursor-pointer rounded-lg border px-3 py-1.5 ${selectedSeasons.includes(s.id) ? "border-brand-600 bg-brand-50 text-brand-700" : "border-border"}`}>
                    <input type="checkbox" className="mr-1.5" checked={selectedSeasons.includes(s.id)} onChange={() => toggleSeason(s.id)} />
                    {s.payload.name} · {formatDate(s.payload.start_date)} to {formatDate(s.payload.end_date)}
                  </label>
                ))}
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label>Monitoring period start<TextInput type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} /></label>
              <label>Monitoring period end<TextInput type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} /></label>
            </div>
            <label className="block">Project (optional — required to submit this calculation for internal review later)
              <Select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                <option value="">No project</option>
                {(projects.data ?? []).map((p) => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
              </Select>
            </label>
            <p className="ui-meta">Accounting pathway: <span className="font-mono">{pathway}</span> (fixed by this field&apos;s registered methodology — never inferred from a crop declaration).</p>
            <Button
              variant="secondary" loading={readiness.isPending}
              disabled={!!contextIssue || busy}
              onClick={() => void perform(checkReadiness)}
            >
              Check readiness
            </Button>
            {contextIssue && <p role="status" className="ui-meta">{contextIssue}</p>}
            {!!unavailableSeasons.length && <Button type="button" variant="secondary" size="sm" onClick={() => setSelectedSeasons((ids) => ids.filter((id) => availableSeasons.some((season) => season.id === id)))}>Remove unavailable season selections</Button>}
            {(readiness.data || preview.data) && !currentReadiness && !currentPreview && !busy && <p role="status" className="ui-meta">The context or inputs changed. Run readiness or a fresh preview for this selection.</p>}
          </fieldset>
        )}
      </Card>

      {currentReadiness && (
        <Card>
          <h3 className="ui-subsection-title mb-3">Readiness checklist</h3>
          <p className="ui-meta mb-3">
            This reflects what this implementation can check automatically, plus any recorded expert
            determinations — it is not a certification of full methodology compliance.
          </p>
          <ReadinessList checklist={currentReadiness.checklist} explain={explainRequirement} highlightedRequirement={requestedRequirement} />
        </Card>
      )}

      {writable && !contextIssue && (
        <Card>
          <h3 id="engine-inputs" className="ui-subsection-title mb-3 scroll-mt-28">Engine inputs</h3>
          <form key={contextKey} className="grid gap-3 sm:grid-cols-2" onChange={() => { setInputRevision((revision) => revision + 1); setPreviewContext(null); }} onSubmit={(e) => {
            e.preventDefault();
            const submitter = (e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
            const action = submitter?.value === "commit" ? "commit" : "preview";
            const form = e.currentTarget;
            void perform(async () => {
              const engineInputs = readEngineInputs(form);
              if (action === "preview") {
                setPreviewContext(previewKey);
                await preview.mutateAsync(buildContext(engineInputs));
                return;
              }
              const body = { ...buildContext(engineInputs), monitoring_run_ids: [], attachment_ids: [],
                supersedes_calculation_id: supersedes || null };
              const out = await commit.mutateAsync({ body, idempotencyKey: crypto.randomUUID() });
              setNotice(out.already_committed ? "Already committed (retried request)." :
                `Saved as ${out.calculation.status.replace("_", " ")} (version ${out.calculation.version}).`);
              await queryClient.invalidateQueries({ queryKey: ["calculations", field.field_id] });
            });
          }}>
            <p className="ui-secondary sm:col-span-2">Manual evidence entry for this monitoring period. No measurements are assumed. Use zero only when the evidence records zero; amendment rates may be zero when no material was applied.</p>
            {pathway === "vm0051_rice_awd" ? (
              <>
                <label className="text-sm">AWD events (evidence-backed)<TextInput name="awd_events" type="number" required min={0} /></label>
                <label className="text-sm">Season length (days)<TextInput name="season_length_days" type="number" required min={1} /></label>
                <label className="text-sm">N input (kg N/ha)<TextInput name="q_n_kg_per_ha" type="number" step="any" required min={0} /></label>
                <label className="text-sm">Pre-season water regime<Select name="preseason_category" required defaultValue="">
                  <option value="">Select documented water regime</option><option value="short">Non-flooded &lt; 180 days</option><option value="long">Non-flooded &gt; 180 days</option>
                </Select></label>
                <label className="text-sm">Baseline amendment type<Select name="baseline_amendment_type" defaultValue="" required><option value="">Select documented amendment</option>{AMENDMENT_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Select></label>
                <label className="text-sm">Baseline amendment rate (t/ha)<TextInput name="baseline_amendment_rate" type="number" step="any" required min={0} /></label>
                <label className="text-sm">Project amendment type<Select name="project_amendment_type" defaultValue="" required><option value="">Select documented amendment</option>{AMENDMENT_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Select></label>
                <label className="text-sm">Project amendment rate (t/ha)<TextInput name="project_amendment_rate" type="number" step="any" required min={0} /></label>
              </>
            ) : (
              <>
                <label className="text-sm">Verification years<TextInput name="verification_years" type="number" step="any" required min={1} /></label>
                <label className="text-sm">Non-permanence risk (%)<TextInput name="non_permanence_risk_pct" type="number" step="any" required min={0} max={100} /></label>
              </>
            )}
            <p className="text-xs text-text-secondary sm:col-span-2">Field area used is always this field&apos;s registered area_ha ({field.area_ha?.toFixed(2)} ha) — it is frozen from the field record, not re-entered here.</p>
            {!!openCalculations.length && (
              <label className="text-sm sm:col-span-2">Correct an existing calculation (optional)
                <Select value={supersedes} onChange={(e) => setSupersedes(e.target.value)}>
                  <option value="">New calculation chain</option>
                  {openCalculations.map((c) => "calculation_id" in c && c.calculation_id && (
                    <option key={c.calculation_id} value={c.calculation_id}>
                      v{c.version} · {c.status} · {formatQueueTimestamp(c.created_at)}
                    </option>
                  ))}
                </Select>
              </label>
            )}
            <label className="ui-label sm:col-span-2"><input type="checkbox" required className="mr-2" />I have checked these values against evidence for the selected period.</label>
            <div className="sm:col-span-2 flex gap-2">
              <Button type="submit" name="action" value="preview" variant="secondary" disabled={busy} loading={preview.isPending}>Preview calculation</Button>
              <Button type="submit" name="action" value="commit" disabled={busy} loading={commit.isPending}>Commit (freeze evidence)</Button>
            </div>
          </form>
        </Card>
      )}

      {currentPreview && (
        <Card>
          <h3 className="ui-subsection-title mb-3">Preview result</h3>
          <p className="text-sm">Calculated estimate (not issued credits): <span className="font-mono">{formatNumber(currentPreview.result.final_issuance as number | null, "tco2e")}</span></p>
          {pathway === "vm0042_alm" && <div className="mt-2 space-y-1 text-sm">
            <p>Annual displacement leakage: {String(currentPreview.result.lk_disp_t ?? "blocked")} tCO2e/year</p>
            <p>Allocated to reductions / removals: {String(currentPreview.result.lk_er_t ?? "—")} / {String(currentPreview.result.lk_cr_t ?? "—")} tCO2e/year</p>
            {!!currentPreview.result.leakage_block_reason && <p className="text-danger-700">{String(currentPreview.result.leakage_block_reason)}</p>}
            <Link className="underline" href={`/fields/${field.field_id}/production-records`}>Manage production and leakage evidence</Link>
            <details><summary>Leakage steps and sources</summary><pre className="overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(currentPreview.result.leakage, null, 2)}</pre></details>
          </div>}
          <div className="mt-3"><ReadinessList checklist={currentPreview.readiness} explain={explainRequirement} highlightedRequirement={requestedRequirement} /></div>
        </Card>
      )}

      {canReview && projectId && !contextIssue && (currentPreview || currentReadiness) && (
        <Card>
          <h3 id="evidence-review" className="ui-subsection-title scroll-mt-28">Record an evidence review</h3>
          <p className="my-2 text-sm text-text-secondary">Project leads and administrators can decide reviewable requirements. Decisions apply to the selected project, dates and current evidence. Changed leakage inputs or production records require a new review.</p>
          <form key={`${contextKey}:${reviewableRequirements.map((item) => item.requirement_id).join()}`} className="space-y-2" onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            void perform(async () => {
              await determination.mutateAsync({ project_id: projectId, accounting_pathway: pathway,
                season_ids: selectedSeasons, monitoring_period_start: periodStart, monitoring_period_end: periodEnd,
                requirement_id: String(data.get("requirement")), status: String(data.get("decision")), reason: String(data.get("reason")) });
              preview.reset();
              setPreviewContext(null);
              await checkReadiness();
              setNotice("Review saved. Run a fresh preview before committing.");
            });
          }}>
            <Select aria-label="Requirement to review" name="requirement" disabled={busy} required defaultValue={reviewableRequirements.some((item) => item.requirement_id === requestedRequirement) ? requestedRequirement : ""}><option value="">Select reviewable requirement</option>
              {reviewableRequirements.map((c) => <option key={c.requirement_id} value={c.requirement_id}>{c.requirement_id}</option>)}
            </Select>
            <Select aria-label="Review decision" name="decision" disabled={busy} defaultValue="satisfied"><option value="satisfied">Evidence accepted</option><option value="not_applicable">Not applicable (where permitted)</option><option value="needs_review">Further review needed</option></Select>
            <TextInput aria-label="Review justification and sources" name="reason" disabled={busy} required placeholder="Decision, source references and justification" />
            <Button type="submit" disabled={busy || !reviewableRequirements.length} loading={determination.isPending}>Record review</Button>
          </form>
        </Card>
      )}

      {projectId && !canReview && (currentPreview || currentReadiness) && <p className="ui-secondary">Evidence review decisions require a project lead or administrator. {members.isPending ? "Checking your project role…" : members.isError ? "Your project role could not be loaded." : "Ask an authorized reviewer to review this context."}</p>}

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="ui-subsection-title">Calculation history</h3>
          {!!legacyCount && <Badge tone="neutral">{legacyCount} legacy (no snapshot)</Badge>}
        </div>
        {history.isLoading ? <p className="mt-2 text-sm">Loading…</p> : history.isError ? <p role="alert">Unable to load calculation history: {history.error.message}</p> : !history.data?.length ? (
          <p className="mt-2 text-sm text-text-secondary">No calculations yet.</p>
        ) : (
          <div className="mt-3 space-y-2">
            {history.data.map((row: CalculationHistoryRow) => (
              <div key={row.legacy ? `legacy-${row.credit_history_id}` : row.calculation_id} className="flex flex-wrap items-center justify-between gap-2 border-t border-border py-2 text-sm first:border-t-0 first:pt-0">
                <div>
                  {row.legacy ? (
                    <Badge tone="neutral">legacy · no snapshot</Badge>
                  ) : (
                    <>
                      <Badge tone={STATUS_TONE[row.status]}>{row.status.replace("_", " ")}</Badge>{" "}
                      <span className="font-mono text-xs text-text-tertiary">v{row.version}</span>
                    </>
                  )}
                  <span className="ml-2">{formatQueueTimestamp(row.created_at)}</span>
                  <span className="ml-2 font-mono">{row.final_issuance == null ? "—" : formatNumber(row.final_issuance, "tco2e")} tCO2e</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {!row.legacy && row.project_id && row.calculation_id && <>
                    {row.status === "draft" && <ExplainButton projectId={row.project_id} request={{ action: "explain_block", field_id: field.field_id, calculation_id: row.calculation_id }}>Explain why blocked</ExplainButton>}
                    <ExplainButton projectId={row.project_id} request={{ action: "diff_since_previous", field_id: field.field_id, calculation_id: row.calculation_id }}>What changed?</ExplainButton>
                  </>}
                  {!row.legacy && row.status === "ready_for_review" && row.project_id && writable && (
                    <Button
                      variant="secondary" size="sm" loading={createSubmission.isPending}
                      onClick={() => void perform(async () => {
                        const sub = await createSubmission.mutateAsync({ project_id: row.project_id!, calculation_id: row.calculation_id! });
                        setNotice(`Submitted for review (submission ${sub.submission_id.slice(0, 8)}…).`);
                      })}
                    >
                      Submit for review
                    </Button>
                  )}
                  {!row.legacy && row.status === "ready_for_review" && !row.project_id && (
                    <span className="ui-meta">Select a project above, then re-commit to submit this for review.</span>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => download(row, row.legacy ? `credit-history-${row.credit_history_id}.json` : `calculation-${row.calculation_id}.json`)}>
                    Download JSON
                  </Button>
                  {!row.legacy && pathway === "vm0042_alm" && <Button variant="ghost" size="sm" onClick={() => void perform(async () => {
                    const blob = await apiFetchBlob(`/calculations/${row.calculation_id}/evidence/pdf`);
                    downloadBlob(blob, `calculation-${row.calculation_id}.pdf`);
                  })}>Download PDF</Button>}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
