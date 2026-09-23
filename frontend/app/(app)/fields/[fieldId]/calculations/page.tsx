"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/app/providers";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput } from "@/components/ui/Field";
import { apiFetch } from "@/lib/api";
import {
  useCalculationHistory, useCommitCalculation, usePreviewCalculation, useReadiness,
} from "@/hooks/use-calculations";
import { useProjects } from "@/hooks/use-projects";
import { useCreateSubmission } from "@/hooks/use-reviews";
import type { AccountingPathway, CalculationHistoryRow, ReadinessCheck } from "@/types/api";
import Link from "next/link";

type SeasonRow = { id: string; payload: { name: string; crops: string[]; start_date: string; end_date: string } };

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

function ReadinessList({ checklist }: { checklist: ReadinessCheck[] }) {
  return (
    <div className="space-y-2">
      {checklist.map((c) => (
        <div key={c.requirement_id} className="flex flex-wrap items-start gap-2 border-t border-border py-2 text-sm first:border-t-0 first:pt-0">
          <Badge tone={READINESS_TONE[c.status]}>{c.status.replace("_", " ")}</Badge>
          <div className="min-w-0 flex-1">
            <p className="font-mono text-xs text-text-tertiary">{c.requirement_id} {c.determination === "expert" && <span className="italic">· expert determination</span>}</p>
            <p>{c.explanation}</p>
            {c.source_reference && <p className="text-xs text-text-tertiary">{c.source_reference}</p>}
            {c.required_evidence && <p className="text-xs text-text-tertiary">Required evidence: {c.required_evidence}</p>}
            {c.implementation_support && c.implementation_support !== "implemented" && (
              <p className="text-xs text-warning-700">Implementation: {c.implementation_support === "unsupported" ? "not implemented by this system" : "partially implemented"}</p>
            )}
            {c.reviewer_authority === "automated_only" && <p className="text-xs text-text-tertiary">Cannot be manually overridden.</p>}
            {c.decided_by && <p className="text-xs text-text-secondary">Recorded decision: {c.reason}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function CalculationsPage() {
  const field = useFieldContext();
  const session = useSession();
  const writable = session?.role === "admin" || session?.role === "analyst";
  const queryClient = useQueryClient();
  const pathway = PATHWAY_BY_FIELD_TYPE[field.field_type];

  const seasons = useQuery({
    queryKey: ["crop-seasons", field.field_id],
    queryFn: () => apiFetch<SeasonRow[]>(`/fields/${field.field_id}/crop-seasons`),
  });
  const history = useCalculationHistory(field.field_id);
  const readiness = useReadiness(field.field_id);
  const preview = usePreviewCalculation(field.field_id);
  const commit = useCommitCalculation(field.field_id);
  const projects = useProjects();
  const createSubmission = useCreateSubmission();

  const [selectedSeasons, setSelectedSeasons] = useState<string[]>([]);
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [supersedes, setSupersedes] = useState("");
  const [projectId, setProjectId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const openCalculations = (history.data ?? []).filter((r) => !r.legacy && r.status !== "superseded");
  const legacyCount = (history.data ?? []).filter((r) => r.legacy).length;

  function toggleSeason(id: string) {
    setSelectedSeasons((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]));
  }

  function buildContext(engineInputs: Record<string, unknown>) {
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
    if (pathway === "vm0051_rice_awd") {
      return {
        awd_events: Number(data.get("awd_events")),
        season_length_days: Number(data.get("season_length_days")),
        q_n_kg_per_ha: Number(data.get("q_n_kg_per_ha")),
        preseason_category: data.get("preseason_category"),
        baseline_amendments: [[data.get("baseline_amendment_type"), Number(data.get("baseline_amendment_rate"))]],
        project_amendments: [[data.get("project_amendment_type"), Number(data.get("project_amendment_rate"))]],
      };
    }
    return {
      verification_years: Number(data.get("verification_years")),
      non_permanence_risk_pct: Number(data.get("non_permanence_risk_pct")),
    };
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Evidence-linked calculations</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Committing here freezes the exact field geometry, crop-season versions, practice records, and
          measurements used into an immutable snapshot. This is separate from the original Carbon Asset Ledger
          (still available under Carbon Asset Ledger) — that flow keeps working unchanged; this one adds
          project/season context, a readiness checklist, and versioned corrections instead of overwriting a result.
        </p>
      </div>

      {error && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{error}</p>}
      {notice && <p role="status" className="text-sm text-success-700">{notice} <Link href="/reviews" className="underline">Go to Reviews</Link></p>}

      <Card>
        <h3 className="mb-3 font-medium">Calculation context</h3>
        {!seasons.data?.length ? (
          <p className="text-sm text-text-secondary">No crop seasons recorded yet — add one under Crop Seasons first.</p>
        ) : (
          <div className="space-y-3 text-sm">
            <div>
              <p className="mb-1.5 font-medium">Crop seasons in this accounting period</p>
              <div className="flex flex-wrap gap-2">
                {seasons.data.map((s) => (
                  <label key={s.id} className={`cursor-pointer rounded-lg border px-3 py-1.5 ${selectedSeasons.includes(s.id) ? "border-brand-600 bg-brand-50 text-brand-700" : "border-border"}`}>
                    <input type="checkbox" className="mr-1.5" checked={selectedSeasons.includes(s.id)} onChange={() => toggleSeason(s.id)} />
                    {s.payload.name} · {s.payload.start_date} to {s.payload.end_date}
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
            <p className="text-xs text-text-tertiary">Accounting pathway: <span className="font-mono">{pathway}</span> (fixed by this field&apos;s registered methodology — never inferred from a crop declaration).</p>
            <Button
              variant="secondary" loading={readiness.isPending}
              disabled={!selectedSeasons.length || !periodStart || !periodEnd}
              onClick={() => void perform(async () => {
                await readiness.mutateAsync({
                  accounting_pathway: pathway, season_ids: selectedSeasons,
                  monitoring_period_start: periodStart, monitoring_period_end: periodEnd,
                });
              })}
            >
              Check readiness
            </Button>
          </div>
        )}
      </Card>

      {readiness.data && (
        <Card>
          <h3 className="mb-3 font-medium">Readiness checklist</h3>
          <p className="mb-3 text-xs text-text-tertiary">
            This reflects what this implementation can check automatically, plus any recorded expert
            determinations — it is not a certification of full methodology compliance.
          </p>
          <ReadinessList checklist={readiness.data.checklist} />
        </Card>
      )}

      {writable && !!selectedSeasons.length && periodStart && periodEnd && (
        <Card>
          <h3 className="mb-3 font-medium">Engine inputs</h3>
          <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => {
            e.preventDefault();
            const submitter = (e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
            const action = submitter?.value === "commit" ? "commit" : "preview";
            const form = e.currentTarget;
            void perform(async () => {
              const engineInputs = readEngineInputs(form);
              if (action === "preview") {
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
            {pathway === "vm0051_rice_awd" ? (
              <>
                <label className="text-sm">AWD events (verified)<TextInput name="awd_events" type="number" required defaultValue={0} /></label>
                <label className="text-sm">Season length (days)<TextInput name="season_length_days" type="number" required defaultValue={120} /></label>
                <label className="text-sm">N input (kg N/ha)<TextInput name="q_n_kg_per_ha" type="number" step="any" required defaultValue={100} /></label>
                <label className="text-sm">Pre-season water regime<Select name="preseason_category" defaultValue="short">
                  <option value="short">Non-flooded &lt; 180 days</option><option value="long">Non-flooded &gt; 180 days</option>
                </Select></label>
                <label className="text-sm">Baseline amendment type<TextInput name="baseline_amendment_type" defaultValue="straw_shortly_before" required /></label>
                <label className="text-sm">Baseline amendment rate (t/ha)<TextInput name="baseline_amendment_rate" type="number" step="any" required defaultValue={5} /></label>
                <label className="text-sm">Project amendment type<TextInput name="project_amendment_type" defaultValue="straw_shortly_before" required /></label>
                <label className="text-sm">Project amendment rate (t/ha)<TextInput name="project_amendment_rate" type="number" step="any" required defaultValue={5} /></label>
              </>
            ) : (
              <>
                <label className="text-sm">Verification years<TextInput name="verification_years" type="number" step="any" required defaultValue={1} /></label>
                <label className="text-sm">Non-permanence risk (%)<TextInput name="non_permanence_risk_pct" type="number" step="any" required defaultValue={20} /></label>
              </>
            )}
            <p className="text-xs text-text-secondary sm:col-span-2">Field area used is always this field&apos;s registered area_ha ({field.area_ha?.toFixed(2)} ha) — it is frozen from the field record, not re-entered here.</p>
            {!!openCalculations.length && (
              <label className="text-sm sm:col-span-2">Correct an existing calculation (optional)
                <Select value={supersedes} onChange={(e) => setSupersedes(e.target.value)}>
                  <option value="">New calculation chain</option>
                  {openCalculations.map((c) => "calculation_id" in c && c.calculation_id && (
                    <option key={c.calculation_id} value={c.calculation_id}>
                      v{c.version} · {c.status} · {new Date(c.created_at).toLocaleString()}
                    </option>
                  ))}
                </Select>
              </label>
            )}
            <div className="sm:col-span-2 flex gap-2">
              <Button type="submit" name="action" value="preview" variant="secondary" loading={preview.isPending}>Preview calculation</Button>
              <Button type="submit" name="action" value="commit" loading={commit.isPending}>Commit (freeze evidence)</Button>
            </div>
          </form>
        </Card>
      )}

      {preview.data && (
        <Card>
          <h3 className="mb-3 font-medium">Preview result</h3>
          <p className="text-sm">Final issuance: <span className="font-mono">{String(preview.data.result.final_issuance ?? "—")}</span></p>
          <div className="mt-3"><ReadinessList checklist={preview.data.readiness} /></div>
        </Card>
      )}

      <Card>
        <div className="flex items-center justify-between">
          <h3 className="font-medium">Calculation history</h3>
          {!!legacyCount && <Badge tone="neutral">{legacyCount} legacy (no snapshot)</Badge>}
        </div>
        {history.isLoading ? <p className="mt-2 text-sm">Loading…</p> : !history.data?.length ? (
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
                  <span className="ml-2">{new Date(row.created_at).toLocaleString()}</span>
                  <span className="ml-2 font-mono">{row.final_issuance ?? "—"} tCO2e</span>
                </div>
                <div className="flex gap-2">
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
                    <span className="text-xs text-text-tertiary">Select a project above, then re-commit to submit this for review.</span>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => download(row, row.legacy ? `credit-history-${row.credit_history_id}.json` : `calculation-${row.calculation_id}.json`)}>
                    Download JSON
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
