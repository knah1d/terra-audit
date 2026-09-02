"use client";

import { Play, Satellite } from "lucide-react";
import { useMemo, useState } from "react";
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
import { isSignalRunAccepted, useLatestSignalRun, useRunSignalAnalysis } from "@/hooks/use-signal";
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
  const [preset, setPreset] = useState<string>(Object.keys(SEASON_PRESETS)[0]);
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [detector, setDetector] = useState<SignalDetector>("threshold");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [result, setResult] = useState<SignalResult | null>(null);

  const run = useRunSignalAnalysis(field.field_id);
  const jobPoll = useJobPoll(jobId ? `/signal-runs/${jobId}` : null);
  // Previously completed run for this field, if any — shown on first
  // visit so a field you already analyzed doesn't come up blank; a fresh
  // handleRun() (below) always overwrites `result` with the new one.
  const latestSignal = useLatestSignalRun(field.field_id);

  const window = preset === "Custom Range" ? { start: customStart, end: customEnd } : SEASON_PRESETS[preset]!;
  const rangeInvalid = !window.start || !window.end || window.end <= window.start;

  // Async path's result lives in the poll query, not local state — no
  // effect-based resync needed (useJobPoll's refetchInterval already stops
  // once status settles). The direct (cache-hit, 200) path stores straight
  // into `result` state since there's no job to poll.
  const jobResult = jobId && jobPoll.data?.status === "done" ? (jobPoll.data.result as unknown as SignalResult) : null;
  const effectiveResult = result ?? jobResult ?? latestSignal.data ?? null;
  const jobError = jobId && jobPoll.data?.status === "error" ? jobPoll.data.error : null;

  async function handleRun() {
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
  }

  const isRunning = run.isPending || (jobId !== null && jobPoll.data?.status !== "done" && jobPoll.data?.status !== "error");

  const awdCount = effectiveResult?.total_awd ?? 0;
  const detectorLabel = useMemo(
    () => DETECTOR_OPTIONS.find((d) => d.value === detector)?.label ?? detector,
    [detector],
  );

  return (
    <div className="flex flex-col gap-6">
      <h2 className="flex items-center gap-2.5 text-lg font-semibold text-text-primary">
        <IconTile icon={Satellite} size="sm" />
        Statistical Signal Analytics
      </h2>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        <div className="surface-card flex flex-col gap-4 rounded-xl p-4">
          <div>
            <FieldLabel>Season</FieldLabel>
            <Select value={preset} onChange={(e) => setPreset(e.target.value)}>
              {Object.keys(SEASON_PRESETS).map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </Select>
          </div>

          {preset === "Custom Range" && (
            <div className="grid grid-cols-2 gap-2">
              <div>
                <FieldLabel>Open</FieldLabel>
                <TextInput type="date" value={customStart} onChange={(e) => setCustomStart(e.target.value)} />
              </div>
              <div>
                <FieldLabel>Close</FieldLabel>
                <TextInput type="date" value={customEnd} onChange={(e) => setCustomEnd(e.target.value)} />
              </div>
            </div>
          )}
          {preset === "Custom Range" && rangeInvalid && (
            <Alert tone="warning">Close date must be after open date.</Alert>
          )}

          <div>
            <FieldLabel>Detector</FieldLabel>
            <Select value={detector} onChange={(e) => setDetector(e.target.value as SignalDetector)}>
              {DETECTOR_OPTIONS.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </Select>
            {detector !== "threshold" && (
              <p className="mt-1 text-xs text-text-tertiary">
                Trained to reproduce the Threshold Gate&apos;s own labels — a proof-of-concept baseline,
                not an independently validated detector.
              </p>
            )}
          </div>

          <Switch checked={forceRefresh} onChange={setForceRefresh} label="Bypass local cache (query live GEE)" />

          <Button icon={Play} onClick={handleRun} loading={isRunning} disabled={rangeInvalid}>
            Run Analytics Engine
          </Button>
        </div>

        <div className="flex flex-col gap-4">
          {run.isError && <Alert tone="danger" title="Run failed">{run.error.message}</Alert>}
          {jobError && <Alert tone="danger" title="Job failed">{jobError}</Alert>}

          {!effectiveResult && !isRunning && (
            <div className="surface-card flex h-full min-h-[200px] items-center justify-center rounded-xl text-sm text-text-tertiary">
              Run the analytics engine to see results.
            </div>
          )}

          {effectiveResult && (
            <>
              {!result && !jobResult && (
                <Alert tone="info">Showing your most recent Signal Analytics run for this field.</Alert>
              )}
              <p className="text-xs text-text-tertiary">Data source: {effectiveResult.cache_source}</p>
              {!effectiveResult.from_phenology && (
                <Alert tone="warning">
                  Phenology markers not detected — season length falls back to a 120-day default.
                </Alert>
              )}
              {effectiveResult.model_fallback_msg && <Alert tone="info">{effectiveResult.model_fallback_msg}</Alert>}

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                <StatCard label="AWD Events" value={String(awdCount)} tone={awdCount > 0 ? "success" : "neutral"} />
                <StatCard label="Sowing Date" value={effectiveResult.sowing_date} />
                <StatCard label="Harvest Date" value={effectiveResult.harvest_date} />
                <StatCard label="Season Length" value={`${effectiveResult.season_length_days} d`} />
                <StatCard label="Detector Used" value={effectiveResult.detector_used} />
              </div>

              <div className="surface-card rounded-xl p-4">
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
