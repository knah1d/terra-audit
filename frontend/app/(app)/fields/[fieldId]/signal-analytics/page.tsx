"use client";

import { useCropSeasons } from "@/hooks/use-crop-seasons";
import { formatDate, parseQueueTimestamp } from "@/lib/format";
import { Play, Satellite } from "lucide-react";
import { useMemo, useState } from "react";
import { AuditTrailTable } from "@/components/signal/AuditTrailTable";
import { SignalTimeseriesChart } from "@/components/signal/SignalTimeseriesChart";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { StatCard } from "@/components/ui/Card";
import { ErrorText, FieldLabel, Select, TextInput } from "@/components/ui/Field";
import { IconTile } from "@/components/ui/IconTile";
import { Switch } from "@/components/ui/Switch";
import { useJobPoll } from "@/hooks/use-job-poll";
import { isSignalRunAccepted, useActiveSignalRuns, useCancelSignalRun, useLatestSignalRun, useRunSignalAnalysis } from "@/hooks/use-signal";
import type { SignalDetector, SignalResult } from "@/types/api";

const SEASON_PRESETS: Record<string, { start: string; end: string } | null> = {
  "Boro 2026 (Jan–May)": { start: "2026-01-01", end: "2026-05-31" },
  "Aman 2025 (Jul–Nov)": { start: "2025-07-01", end: "2025-11-30" },
  "Pre-Kharif 2025 (Mar–Jun)": { start: "2025-03-01", end: "2025-06-30" },
  "Boro 2025 (Jan–May)": { start: "2025-01-01", end: "2025-05-31" },
  "Custom Range": null,
};

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
  const [preset, setPreset] = useState<string>("Custom Range");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [detector, setDetector] = useState<SignalDetector>("threshold");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<SignalResult | null>(null);

  const run = useRunSignalAnalysis(field.field_id);
  const cancel = useCancelSignalRun(field.field_id);
  const jobPoll = useJobPoll(jobId ? `/signal-runs/${jobId}` : null);
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
      const savedPreset = Object.entries(SEASON_PRESETS).find(([, range]) => range?.start === request.window_start && range.end === request.window_end)?.[0];
      setPreset(savedPreset || "Custom Range");
      setCustomStart(request.window_start);
      setCustomEnd(request.window_end);
      setDetector(request.detector);
      setForceRefresh(request.force_refresh);
      setJobId(active.job_id);
    }
  }

  const selectedSeason = currentSeasons.find(s => `season:${s.season_id || s.id}` === preset);
  const window = selectedSeason ? { start: selectedSeason.payload.start_date, end: selectedSeason.payload.end_date } : preset === "Custom Range" ? { start: customStart, end: customEnd } : SEASON_PRESETS[preset] ?? { start: "", end: "" };
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
    } catch {
      // The mutation error is displayed below; retain all selected inputs.
    }
  }

  const jobStatus = jobId ? jobPoll.data?.status : null;
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
        Statistical Signal Analytics
      </h2>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        <div className="ui-card flex flex-col gap-4">
          <div>
            <FieldLabel htmlFor="field-1">Analysis window</FieldLabel>
            <Select id="field-1" value={preset} onChange={(e) => setPreset(e.target.value)}>
              {currentSeasons.map(s => <option key={s.season_id || s.id} value={`season:${s.season_id || s.id}`}>{s.payload.name} · {formatDate(s.payload.start_date)} to {formatDate(s.payload.end_date)}</option>)}
              {Object.keys(SEASON_PRESETS).map((p) => (
                <option key={p} value={p}>{p === "Custom Range" ? p : `Preset: ${p}`}</option>
              ))}
            </Select>
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
          {preset === "Custom Range" && rangeInvalid && (
            <ErrorText>Close date must be after open date.</ErrorText>
          )}

          <div>
            <FieldLabel htmlFor="field-4">Detector</FieldLabel>
            <Select id="field-4" value={detector} onChange={(e) => setDetector(e.target.value as SignalDetector)}>
              {DETECTOR_OPTIONS.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </Select>
            {detector !== "threshold" && (
              <p className="ui-meta mt-1">
                Trained to reproduce the Threshold Gate&apos;s own labels — a proof-of-concept baseline,
                not an independently validated detector.
              </p>
            )}
          </div>

          <Switch checked={forceRefresh} onChange={setForceRefresh} label="Bypass local cache (query live GEE)" />

          <Button icon={Play} onClick={handleRun} loading={run.isPending || (processing && !jobPoll.isError)} disabled={rangeInvalid || jobActive || !activeRuns.isFetchedAfterMount || activeRuns.isError}>
            {jobStatus === "pending" ? "Analysis queued" : "Run Analytics Engine"}
          </Button>
          {jobActive && <Button variant="secondary" loading={cancel.isPending} disabled={jobStatus === "cancel_requested"} onClick={() => {
            if (jobId) cancel.mutate(jobId, { onSuccess: () => { void jobPoll.refetch(); } });
          }}>Cancel analysis</Button>}
        </div>

        <div className="flex flex-col gap-4">
          {activeRuns.isPending && <Alert tone="info">Checking for an existing analysis…</Alert>}
          {activeRuns.isError && <Alert tone="danger" title="Unable to restore analysis status">{activeRuns.error.message} <button className="underline" onClick={() => void activeRuns.refetch()}>Retry</button></Alert>}
          {run.isPending && <Alert tone="info" title="Submitting analysis">Checking cached observations and preparing the request.</Alert>}
          {jobStatus === "pending" && !pendingStalled && <Alert tone="info" title="Analysis queued">Waiting for a worker to start processing.</Alert>}
          {pendingStalled && <Alert tone="warning" title="Still waiting for a worker">Processing has not started. Your worker must accept satellite analytics jobs; an AI-explanation-only worker cannot process this request. Check Worker &amp; queue, and keep your worker computer awake. Your selected season and detector are preserved.</Alert>}
          {jobStatus === "running" && <Alert tone="info" title={STAGES[jobPoll.data?.progress?.stage ?? ""] || "Analysis in progress"}>Results will update when processing finishes. You can reopen this field to resume checking the active job.</Alert>}
          {jobStatus === "cancel_requested" && <Alert tone="info" title="Cancellation requested">The worker will stop at its next cancellation checkpoint.</Alert>}
          {jobStatus === "cancelled" && <Alert tone="info" title="Analysis cancelled">You can submit a new analysis when ready.</Alert>}
          {jobPoll.isError && <Alert tone="danger" title="Unable to check analysis status">{jobPoll.error.message}</Alert>}
          {jobPoll.isError && jobActive && <Button variant="secondary" onClick={() => void jobPoll.refetch()}>Retry status check</Button>}
          {cancel.isError && <Alert tone="danger" title="Unable to cancel analysis">{cancel.error.message}</Alert>}
          {run.isError && <Alert tone="danger" title="Run failed">{run.error.message}</Alert>}
          {jobError && <Alert tone="danger" title="Job failed">{jobError}</Alert>}

          {!effectiveResult && !isRunning && (
            <div className="ui-card flex h-full min-h-[200px] items-center justify-center text-sm text-text-tertiary">
              Run the analytics engine to see results.
            </div>
          )}

          {effectiveResult && (
            <>
              <p className="text-xs text-text-secondary">Showing {!result && !jobResult && "your most recent run · "}{effectiveResult.window_start} – {effectiveResult.window_end} · {effectiveResult.detector_used} · Source: {effectiveResult.cache_source}{!effectiveResult.from_phenology && " · Phenology markers not detected, season length uses the 120-day default"}</p>
              {effectiveResult.timings_seconds && <details className="text-xs text-text-secondary"><summary className="cursor-pointer">Worker processing times</summary><div className="mt-2 space-y-1">{Object.entries(effectiveResult.timings_seconds).map(([stage, seconds]) => <p key={stage}>{STAGES[stage] || stage.replaceAll("_", " ")}: {seconds.toFixed(2)} s</p>)}<p>These timings exclude queue waiting and the final result write.</p></div></details>}
              {effectiveResult.model_fallback_msg && <Alert tone="info">{effectiveResult.model_fallback_msg}</Alert>}

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                <StatCard label="AWD Events" value={String(awdCount)} tone={awdCount > 0 ? "success" : "neutral"} />
                <StatCard label="Sowing Date" value={effectiveResult.sowing_date} />
                <StatCard label="Harvest Date" value={effectiveResult.harvest_date} />
                <StatCard label="Season Length" value={`${effectiveResult.season_length_days} d${effectiveResult.from_phenology ? "" : " (default)"}`} />
                <StatCard label="Detector Used" value={effectiveResult.detector_used} />
              </div>

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
