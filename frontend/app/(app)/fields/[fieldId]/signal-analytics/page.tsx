"use client";

import { useCropSeasons } from "@/hooks/use-crop-seasons";
import { formatDate, parseQueueTimestamp } from "@/lib/format";
import { Play, Satellite } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSession } from "@/app/providers";
import { useToast } from "@/components/ui/Toast";
import { ExplainButton } from "@/components/ai/ExplainDrawer";
import { AuditTrailTable } from "@/components/signal/AuditTrailTable";
import { SignalTimeseriesChart } from "@/components/signal/SignalTimeseriesChart";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { StatCard } from "@/components/ui/Card";
import { FieldLabel, Select, TextInput } from "@/components/ui/Field";
import { IconTile } from "@/components/ui/IconTile";
import { Switch } from "@/components/ui/Switch";
import { useJobPoll } from "@/hooks/use-job-poll";
import { invalidateSignalViews, isSignalRunAccepted, useActiveSignalRuns, useCancelSignalRun, useLatestSignalRun, useRunSignalAnalysis } from "@/hooks/use-signal";
import type { SignalDetector, SignalResult } from "@/types/api";

type SeasonPreset = { start: string; end: string; inProgress: boolean };

// Bangladesh rice seasons (start/end month, 1-based).
const SEASONS = [
  { name: "Boro", startMonth: 1, endMonth: 5, months: "Jan–May" },
  { name: "Pre-Kharif", startMonth: 3, endMonth: 6, months: "Mar–Jun" },
  { name: "Aman", startMonth: 7, endMonth: 11, months: "Jul–Nov" },
];

function isoDate(year: number, month: number, day: number) {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/** The most recent occurrence of each season relative to `today` — the
 * one in progress, else the last completed one — newest first. An
 * in-progress season ends today rather than at its calendar end: signal
 * observations are cached by exact window, so a future end date would
 * cache a partial season and keep reusing it. */
function buildSeasonPresets(today: Date): Record<string, SeasonPreset | null> {
  const todayIso = isoDate(today.getFullYear(), today.getMonth() + 1, today.getDate());
  const presets = SEASONS.map(({ name, startMonth, endMonth, months }) => {
    let year = today.getFullYear();
    if (todayIso < isoDate(year, startMonth, 1)) year -= 1;
    const start = isoDate(year, startMonth, 1);
    const end = isoDate(year, endMonth, new Date(year, endMonth, 0).getDate());
    const inProgress = todayIso <= end;
    return {
      label: inProgress ? `${name} ${year} (in progress)` : `${name} ${year} (${months})`,
      preset: { start, end: inProgress ? todayIso : end, inProgress },
    };
  }).sort((a, b) => b.preset.start.localeCompare(a.preset.start));
  return { ...Object.fromEntries(presets.map((p) => [p.label, p.preset])), "Custom Range": null };
}

const DETECTOR_OPTIONS: Array<{ value: SignalDetector; label: string }> = [
  { value: "threshold", label: "Threshold Gate (rule-based)" },
  { value: "random_forest", label: "Random Forest (AI baseline)" },
  { value: "xgboost", label: "XGBoost (AI baseline)" },
];

export default function SignalAnalyticsPage() {
  const field = useFieldContext();
  return <SignalAnalyticsView key={field.field_id} />;
}

const STAGES: Record<string, string> = {
  checking_cache: "Checking saved observations",
  fetching_satellite_observations: "Fetching satellite observations from Earth Engine",
  saving_observations: "Saving satellite observations",
  analyzing_observations: "Analyzing observations",
  saving_result: "Saving analysis result",
  progress_checkpoints: "Cancellation, lease and progress checks",
};

function SignalAnalyticsView() {
  const field = useFieldContext();
  const seasons = useCropSeasons(field.field_id);
  const currentSeasons = seasons.data ?? [];
  const [seasonPresets] = useState(() => buildSeasonPresets(new Date()));
  const [preset, setPreset] = useState<string>("Custom Range");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [detector, setDetector] = useState<SignalDetector>("threshold");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<SignalResult | null>(null);

  const run = useRunSignalAnalysis(field.field_id);
  const cancel = useCancelSignalRun(field.field_id);
  const session = useSession();
  const toast = useToast();
  // Running or cancelling an analysis is analyst/admin work (server: require_writer).
  const writable = session?.role === "admin" || session?.role === "analyst";
  const jobPoll = useJobPoll(jobId ? `/signal-runs/${jobId}` : null);
  const queryClient = useQueryClient();
  const jobDone = jobId !== null && jobPoll.data?.status === "done";
  // A queued run became the field's latest saved run: refresh views that show it.
  useEffect(() => {
    if (jobDone) invalidateSignalViews(queryClient, field.field_id);
  }, [jobDone, queryClient, field.field_id]);
  // Previously completed run for this field, if any — shown on first
  // visit so a field you already analyzed doesn't come up blank; a fresh
  // handleRun() (below) always overwrites `result` with the new one.
  const latestSignal = useLatestSignalRun(field.field_id);
  const activeRuns = useActiveSignalRuns(field.field_id);
  const [recoveryAttempted, setRecoveryAttempted] = useState(false);
  // Recover once from fresh query data. Updating this component's state
  // during render avoids showing one frame of default inputs before an
  // effect restores the in-flight request. The guard prevents loops.
  if (!recoveryAttempted && activeRuns.isFetchedAfterMount && activeRuns.data) {
    setRecoveryAttempted(true);
    const active = activeRuns.data[0];
    if (active) {
      const request = active.request;
      const savedPreset = Object.entries(seasonPresets).find(([, range]) => range?.start === request.window_start && range.end === request.window_end)?.[0];
      setPreset(savedPreset || "Custom Range");
      setCustomStart(request.window_start);
      setCustomEnd(request.window_end);
      setDetector(request.detector);
      setForceRefresh(request.force_refresh);
      setJobId(active.job_id);
    }
  }

  const selectedSeason = currentSeasons.find(s => `season:${s.season_id || s.id}` === preset);
  const window = selectedSeason ? { start: selectedSeason.payload.start_date, end: selectedSeason.payload.end_date } : preset === "Custom Range" ? { start: customStart, end: customEnd } : seasonPresets[preset] ?? { start: "", end: "" };
  const rangeInvalid = !window.start || !window.end || window.end <= window.start;

  // Async path's result lives in the poll query, not local state — no
  // effect-based resync needed (useJobPoll's refetchInterval already stops
  // once status settles). The direct (cache-hit, 200) path stores straight
  // into `result` state since there's no job to poll.
  const jobResult = jobId && jobPoll.data?.status === "done" ? (jobPoll.data.result as unknown as SignalResult) : null;
  const effectiveResult = result ?? jobResult ?? latestSignal.data ?? null;
  const jobError = jobId && jobPoll.data?.status === "error" ? jobPoll.data.error : null;

  async function handleRun() {
    if (isRunning || rangeInvalid) return;
    setRecoveryAttempted(true);
    try {
      setJobId(null);
      setResult(null);
      const body = await run.mutateAsync({
        window_start: window.start,
        window_end: window.end,
        detector,
        force_refresh: forceRefresh,
      });
      if (isSignalRunAccepted(body)) {
        setJobId(body.job_id);
      } else {
        setResult(body);
      }
    } catch (e) {
      toast.error(e, "Couldn't start the analysis"); // all selected inputs are kept
    }
  }

  const jobStatus = jobId ? jobPoll.data?.status : null;
  // Announce the finish once per job (the user may be looking elsewhere on the page).
  const announced = useRef<string | null>(null);
  useEffect(() => {
    if (!jobId || announced.current === jobId) return;
    if (jobStatus === "done") { announced.current = jobId; toast.success("Analysis complete", { description: "The results are saved and ready for Calculations." }); }
    if (jobStatus === "error") { announced.current = jobId; toast.error(new Error(jobPoll.data?.error ?? "The analysis failed"), "Analysis failed"); }
  }, [jobId, jobStatus, jobPoll.data?.error, toast]);
  const jobActive = jobId !== null && !["done", "error", "cancelled"].includes(jobStatus ?? "");
  const isRunning = run.isPending || jobActive;
  const processing = jobStatus === "running" || jobStatus === "cancel_requested";
  // Escalate to a warning only once a queued job has gone ~60s without a worker picking it up.
  const queuedAt = parseQueueTimestamp(jobPoll.data?.created_at)?.getTime();
  const pendingStalled = jobStatus === "pending" && queuedAt !== undefined && jobPoll.dataUpdatedAt - queuedAt > 60_000;

  const awdCount = effectiveResult?.total_awd ?? 0;
  const detectorLabel = useMemo(
    () => DETECTOR_OPTIONS.find((d) => d.value === detector)?.label ?? detector,
    [detector],
  );

  return (
    <div className="ui-container-wide flex flex-col gap-6">
      <h2 className="ui-section-title flex items-center gap-3">
        <IconTile icon={Satellite} size="sm" />
        Signal Analytics
      </h2>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        <div className="ui-card flex flex-col gap-4">
          <div>
            <FieldLabel htmlFor="field-1">Analysis window</FieldLabel>
            <Select id="field-1" value={preset} onChange={(e) => setPreset(e.target.value)}>
              {currentSeasons.map(s => <option key={s.season_id || s.id} value={`season:${s.season_id || s.id}`}>{s.payload.name} · {formatDate(s.payload.start_date)} to {formatDate(s.payload.end_date)}</option>)}
              {Object.keys(seasonPresets).map((p) => (
                <option key={p} value={p}>{p === "Custom Range" ? p : `Preset: ${p}`}</option>
              ))}
            </Select>
            {seasonPresets[preset]?.inProgress && (
              <p className="ui-meta mt-1">In progress — results so far.</p>
            )}
          </div>

          {preset === "Custom Range" && (
            <div className="grid grid-cols-2 gap-2">
              <div>
                <FieldLabel htmlFor="field-2">Open</FieldLabel>
                <TextInput id="field-2" type="date" value={customStart} onChange={(e) => setCustomStart(e.target.value)} />
              </div>
              <div>
                <FieldLabel htmlFor="field-3">Close</FieldLabel>
                <TextInput id="field-3" type="date" value={customEnd} onChange={(e) => setCustomEnd(e.target.value)} />
              </div>
            </div>
          )}

          <div>
            <FieldLabel htmlFor="field-4">Detector</FieldLabel>
            <Select id="field-4" value={detector} onChange={(e) => setDetector(e.target.value as SignalDetector)}>
              {DETECTOR_OPTIONS.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </Select>
            {detector !== "threshold" && (
              <p className="ui-meta mt-1">Baseline only — not independently validated.</p>
            )}
          </div>

          <Switch checked={forceRefresh} onChange={setForceRefresh} label="Bypass local cache (query live GEE)" />

          {writable && <Button icon={Play} onClick={handleRun} loading={run.isPending || (processing && !jobPoll.isError)} disabled={rangeInvalid || jobActive || !activeRuns.isFetchedAfterMount || activeRuns.isError}>
            {jobStatus === "pending" ? "Analysis queued" : "Run Analytics Engine"}
          </Button>}
          {writable && jobActive && <Button variant="secondary" loading={cancel.isPending} disabled={jobStatus === "cancel_requested"} onClick={() => {
            if (jobId) cancel.mutate(jobId, {
              onSuccess: () => { void jobPoll.refetch(); toast.info("Cancellation requested"); },
              onError: (e) => toast.error(e, "Couldn't cancel the analysis"),
            });
          }}>Cancel analysis</Button>}
          {!writable && <p className="ui-meta">Analysts and administrators can run analyses. You can view the saved results.</p>}
        </div>

        <div className="flex flex-col gap-4">
          {activeRuns.isPending && <Alert tone="info">Checking for an existing analysis…</Alert>}
          {activeRuns.isError && <Alert tone="danger" title="Unable to restore analysis status">{activeRuns.error.message} <button className="underline" onClick={() => void activeRuns.refetch()}>Retry</button></Alert>}
          {run.isPending && <Alert tone="info" title="Submitting analysis">Checking cached observations and preparing the request.</Alert>}
          {jobStatus === "pending" && !pendingStalled && <Alert tone="info" title="Analysis queued">Waiting for a worker to start processing.</Alert>}
          {pendingStalled && <Alert tone="warning" title="Still waiting for a worker">Check that a worker is running.</Alert>}
          {jobStatus === "running" && <Alert tone="info" title={STAGES[jobPoll.data?.progress?.stage ?? ""] || "Analysis in progress"}>Results appear when finished.</Alert>}
          {jobStatus === "cancel_requested" && <Alert tone="info" title="Cancellation requested">The worker will stop at its next cancellation checkpoint.</Alert>}
          {jobStatus === "cancelled" && <Alert tone="info" title="Analysis cancelled">You can submit a new analysis when ready.</Alert>}
          {jobPoll.isError && <Alert tone="danger" title="Unable to check analysis status">{jobPoll.error.message}</Alert>}
          {jobPoll.isError && jobActive && <Button variant="secondary" onClick={() => void jobPoll.refetch()}>Retry status check</Button>}
          {jobError && <Alert tone="danger" title="Job failed">{jobError}</Alert>}

          {!effectiveResult && !isRunning && (
            <div className="ui-card flex h-full min-h-[200px] items-center justify-center text-sm text-text-tertiary">
              Run the analytics engine to see results.
            </div>
          )}

          {effectiveResult && (
            <>
              <p className="text-xs text-text-secondary">Showing {!result && !jobResult && "your most recent run · "}{effectiveResult.window_start} – {effectiveResult.window_end} · {effectiveResult.detector_used} · Source: {effectiveResult.cache_source}{!effectiveResult.from_phenology && " · Phenology markers not detected, season length uses the 120-day default"}</p>
              {effectiveResult.model_fallback_msg && <Alert tone="info">{effectiveResult.model_fallback_msg}</Alert>}

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                <StatCard label="AWD Events" value={String(awdCount)} tone={awdCount > 0 ? "success" : "neutral"} />
                <StatCard label="Sowing Date" value={effectiveResult.sowing_date} />
                <StatCard label="Harvest Date" value={effectiveResult.harvest_date} />
                <StatCard label="Season Length" value={`${effectiveResult.season_length_days} d${effectiveResult.from_phenology ? "" : " (default)"}`} />
                <StatCard label="Detector Used" value={effectiveResult.detector_used} />
              </div>
              {/* AI explanation of the saved rule-based run (needs the field's project). */}
              {field.current_project && effectiveResult.detector_used === "Threshold Gate (rule-based)" && (
                <div className="flex flex-wrap items-center gap-2 text-sm text-text-secondary">
                  <span>Wondering why?</span>
                  <ExplainButton projectId={field.current_project.project_id} request={{
                    action: "explain_signal_run", field_id: field.field_id,
                    window_start: effectiveResult.window_start, window_end: effectiveResult.window_end,
                  }}>Why {awdCount} drydown{awdCount === 1 ? "" : "s"}?</ExplainButton>
                </div>
              )}

              <div className="ui-card">
                <SignalTimeseriesChart
                  rows={effectiveResult.timeseries as never}
                  awdDates={effectiveResult.awd_dates}
                />
              </div>

              <div>
                <p className="mb-2 text-sm font-medium text-text-primary">Compliance Audit Trail Ledger</p>
                <AuditTrailTable rows={effectiveResult.timeseries} />
              </div>
            </>
          )}
        </div>
      </div>
      <p className="sr-only">{detectorLabel}</p>
    </div>
  );
}
