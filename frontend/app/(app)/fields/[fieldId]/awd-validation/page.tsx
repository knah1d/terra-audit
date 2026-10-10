"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ExplainButton } from "@/components/ai/ExplainDrawer";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import type { ResearchMetrics } from "@/components/ai/AwdModelPerformance";
import { apiFetch, ApiError } from "@/lib/api";

type Detector = {
  window_start: string | null;
  window_end: string | null;
  detector_used: string | null;
  candidate_drydowns: number | null;
  source: string | null;
};
type Comparison = {
  field_id: string;
  research_benchmark: ResearchMetrics | null;
  existing_signal: Detector | null;
  message: string;
};
type Prediction = {
  predicted_class: "AWD" | "PTR";
  awd_score: number;
  score_calibrated: false;
  window_start: string;
  window_end: string;
  observations: number;
  max_gap_days: number;
  relative_orbit: number | null;
  embedding_year: number;
  model_version: string;
  // Always the same Signal Analytics run (same field, same window) as the detector card.
  comparison: {
    status: "compared" | "no_detector_run";
    detector_category: "continuous_flooding" | "single_drainage" | "multiple_drainage" | null;
    detector_drydowns: number | null;
    ml_is_awd: boolean;
    agrees: boolean | null;
  };
};

const CATEGORY_LABELS: Record<string, string> = {
  continuous_flooding: "Continuous flooding (0 drydowns, SF_w 1.00)",
  single_drainage: "Single drainage (1 drydown, SF_w 0.71)",
  multiple_drainage: "Multiple drainage / AWD (≥2 drydowns, SF_w 0.55)",
};

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function ExternalAWDValidationPage() {
  const field = useFieldContext();
  const fieldPath = `/fields/${encodeURIComponent(field.field_id)}`;
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["external-awd-comparison", field.field_id],
    queryFn: () => apiFetch<Comparison>(`${fieldPath}/awd-external-comparison`),
  });
  const prediction = useMutation({
    mutationFn: () => apiFetch<Prediction>(`${fieldPath}/awd-external-prediction`, { method: "POST" }),
  });
  const metrics = data?.research_benchmark ?? null;
  const detector = data?.existing_signal ?? null;
  const result = prediction.data;
  // A 422 is an expected "no prediction" outcome (no run yet, too few observations, embedding not published).
  const predictionWarning = prediction.error instanceof ApiError && prediction.error.status === 422;

  return (
    <main className="ui-container space-y-6">
      <div>
        <h2 className="ui-section-title">AWD Check (ML)</h2>
      </div>
      {isPending && <Alert tone="info">Loading the last signal run…</Alert>}
      {error && <Alert tone="danger" title="Unable to load comparison">
        {error.message} <button type="button" className="underline" onClick={() => void refetch()}>Retry</button>
      </Alert>}
      {data && <>
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="ui-card space-y-3">
            <h3 className="ui-subsection-title">Latest Signal Analytics run</h3>
            {detector ? <>
              <p className="text-sm">Candidate drydowns: <strong>{detector.candidate_drydowns ?? "—"}</strong></p>
              {detector.candidate_drydowns !== null && (
                <p className="text-sm">VM0051 category: <strong>{CATEGORY_LABELS[
                  detector.candidate_drydowns === 0 ? "continuous_flooding"
                    : detector.candidate_drydowns === 1 ? "single_drainage" : "multiple_drainage"]}</strong></p>
              )}
              <p className="text-sm text-text-secondary">
                Window: {detector.window_start ?? "—"} – {detector.window_end ?? "—"}
                {result && " (same window as the ML classification)"}
              </p>
              <p className="text-xs text-text-tertiary">Detector: {detector.detector_used ?? "Unknown"} · Source: {detector.source ?? "Unknown"}</p>
            </> : <p className="text-sm text-text-secondary">No saved signal run for this field.</p>}
            <Link className="text-sm underline" href={`${fieldPath}/signal-analytics`}>Open Signal Analytics</Link>
          </section>

          <section className="ui-card space-y-3">
            <h3 className="ui-subsection-title">ML practice classification</h3>
            {!metrics ? (
              <p className="text-sm text-text-secondary">No trained model is installed on this server.</p>
            ) : <>
              <Button type="button" onClick={() => prediction.mutate()} loading={prediction.isPending} disabled={!detector}>
                {result ? "Run again" : "Run ML classification"}
              </Button>
              {!detector && <p className="ui-meta">Run Signal Analytics first.</p>}
              {prediction.error && <Alert tone={predictionWarning ? "warning" : "danger"}>
                {prediction.error instanceof ApiError ? prediction.error.detail : prediction.error.message}
              </Alert>}
              {result && !prediction.error && <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="ui-meta">Classification</p>
                    <p className="text-xl font-semibold">{result.comparison.ml_is_awd ? "AWD" : "Not AWD"}</p>
                  </div>
                  <div>
                    <p className="ui-meta">AWD score</p>
                    <p className="text-xl font-semibold tabular-nums">{pct(result.awd_score)}</p>
                  </div>
                </div>
                <p className="text-xs text-text-secondary">
                  Window {result.window_start} – {result.window_end} · {result.observations} ascending Sentinel-1
                  observations (largest gap {result.max_gap_days} days) · relative orbit {result.relative_orbit ?? "—"} ·
                  Satellite Embedding {result.embedding_year}
                </p>
                <p className="text-sm">
                  <strong>Compared with detector: </strong>
                  {result.comparison.status === "no_detector_run" ? "no detector run to compare." : <>
                    {result.comparison.agrees ? "they agree" : "they disagree"} — ML says{" "}
                    {result.comparison.ml_is_awd ? "AWD" : "not AWD"} ({pct(result.awd_score)}{" "}
                    {result.comparison.ml_is_awd ? "≥" : "<"} 50%); the detector found{" "}
                    {result.comparison.detector_drydowns} drydown{result.comparison.detector_drydowns === 1 ? "" : "s"}{" "}
                    ({result.comparison.detector_category === "multiple_drainage" ? "AWD: multiple drainage"
                      : "not AWD: " + (result.comparison.detector_category === "single_drainage"
                        ? "single drainage" : "continuous flooding")}).
                  </>}
                </p>
                {/* AI explanation of this exact prediction vs the detector (needs the field's project). */}
                {field.current_project && result.comparison.status === "compared" && (
                  <ExplainButton projectId={field.current_project.project_id}
                    request={{ action: "explain_awd_check", field_id: field.field_id }}>
                    {result.comparison.agrees ? "Why do they agree?" : "Why do they disagree?"}
                  </ExplainButton>
                )}
              </>}
            </>}
          </section>
        </div>

      </>}
    </main>
  );
}
