"use client";

import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { apiFetch, ApiError } from "@/lib/api";

type PerClass = { not_awd: number; awd: number };
type ResearchMetrics = {
  benchmark_version: string;
  source_url: string;
  source_file?: string;
  target: string;
  split_strategy: string;
  rows_awd_ptr: number;
  duplicate_rows_removed: number;
  train_rows: number;
  test_rows: number;
  accuracy: number;
  balanced_accuracy: number;
  precision: PerClass;
  recall: PerClass;
  f1: PerClass;
  support: PerClass;
  roc_auc: number;
  brier_score: number;
  repeated_cv_5x5: { accuracy_mean: number; accuracy_std: number; roc_auc_mean: number; roc_auc_std: number };
  confusion_matrix: number[][];
  limitations: string[];
};
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
  relative_orbit: number | null;
  embedding_year: number;
  model_version: string;
  comparison: {
    status: "compared" | "different_windows" | "no_detector_run";
    detector_category: "continuous_flooding" | "single_drainage" | "multiple_drainage" | null;
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

  return (
    <main className="ui-container space-y-6">
      <div>
        <h2 className="ui-section-title">AWD practice classification (experimental)</h2>
        <p className="mt-1 text-sm text-text-secondary">
          A random forest trained on real research labels, shown alongside the existing rule-based
          detector. Nothing on this page changes drydown counting, carbon calculations, readiness or issuance.
        </p>
      </div>
      {/* <Alert tone="warning" title="Practice classification, not a verified AWD cycle count">
        The model labels a whole season as AWD-like or PTR-like (conventional puddled transplanting). It does
        not count drying events, and it has not been validated on Bangladesh fields.
      </Alert> */}
      {isPending && <Alert tone="info">Loading model metrics and last signal run…</Alert>}
      {error && <Alert tone="danger" title="Unable to load comparison">
        {error.message} <button type="button" className="underline" onClick={() => void refetch()}>Retry</button>
      </Alert>}
      {data && <>
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="ui-card space-y-3">
            <h3 className="ui-subsection-title">Rule-based detector (existing)</h3>
            {detector ? <>
              <p className="text-sm">Candidate drydowns: <strong>{detector.candidate_drydowns ?? "—"}</strong></p>
              {detector.candidate_drydowns !== null && (
                <p className="text-sm">VM0051 category: <strong>{CATEGORY_LABELS[
                  detector.candidate_drydowns === 0 ? "continuous_flooding"
                    : detector.candidate_drydowns === 1 ? "single_drainage" : "multiple_drainage"]}</strong></p>
              )}
              <p className="text-sm text-text-secondary">Window: {detector.window_start ?? "—"} – {detector.window_end ?? "—"}</p>
              <p className="text-xs text-text-tertiary">Detector: {detector.detector_used ?? "Unknown"} · Source: {detector.source ?? "Unknown"}</p>
            </> : <p className="text-sm text-text-secondary">No saved signal run for this field.</p>}
            <Link className="text-sm underline" href={`${fieldPath}/signal-analytics`}>Open Signal Analytics</Link>
          </section>

          <section className="ui-card space-y-3">
            <h3 className="ui-subsection-title">ML practice classification</h3>
            {!metrics ? (
              <p className="text-sm text-text-secondary">No trained model is installed on this server.</p>
            ) : <>
              <Button type="button" onClick={() => prediction.mutate()} loading={prediction.isPending}>
                {result ? "Run again" : "Run ML classification"}
              </Button>
              {prediction.error && <Alert tone="danger">
                {prediction.error instanceof ApiError ? prediction.error.detail : prediction.error.message}
              </Alert>}
              {result && <>
                <div>
                  <p className="ui-meta">AWD score</p>
                  <p className="text-xl font-semibold tabular-nums">{pct(result.awd_score)}</p>
                  <p className="ui-meta">Share of the model&apos;s trees voting AWD — not a calibrated probability.</p>
                </div>
                <p className="text-xs text-text-secondary">
                  Window {result.window_start} – {result.window_end} · {result.observations} ascending observations ·
                  relative orbit {result.relative_orbit ?? "—"} · Satellite Embedding {result.embedding_year}
                </p>
                <p className="text-sm">
                  <strong>Compared with detector: </strong>
                  {result.comparison.status === "no_detector_run" ? "no detector run to compare."
                    : <>
                      {result.comparison.agrees ? "agrees" : "disagrees"} at practice level
                      (AWD score ≥ 50% ↔ multiple drainage).
                      {result.comparison.status === "different_windows" &&
                        " Caution: the detector run covers a different date window."}
                    </>}
                </p>
              </>}
            </>}
          </section>
        </div>

        {metrics && (
          <section className="ui-card space-y-3">
            <h3 className="ui-subsection-title">Model performance on real research data</h3>
            <p className="text-sm text-text-secondary">
              {metrics.rows_awd_ptr} labelled plots (AWD vs PTR, Punjab, India, Kharif 2024;{" "}
              {metrics.duplicate_rows_removed} duplicate rows removed) · {metrics.train_rows} train / {metrics.test_rows} held-out test.
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div><p className="ui-meta">Held-out accuracy</p><p className="text-xl font-semibold tabular-nums">{pct(metrics.accuracy)}</p></div>
              <div><p className="ui-meta">Balanced accuracy</p><p className="text-xl font-semibold tabular-nums">{pct(metrics.balanced_accuracy)}</p></div>
              <div><p className="ui-meta">ROC-AUC</p><p className="text-xl font-semibold tabular-nums">{metrics.roc_auc.toFixed(3)}</p></div>
              <div><p className="ui-meta">Repeated CV accuracy</p>
                <p className="text-xl font-semibold tabular-nums">{pct(metrics.repeated_cv_5x5.accuracy_mean)}
                  <span className="text-sm font-normal"> ± {pct(metrics.repeated_cv_5x5.accuracy_std)}</span></p></div>
            </div>
            <div className="overflow-x-auto">
              <table className="text-sm">
                <thead><tr className="text-left text-text-secondary">
                  <th className="pr-6">Class</th><th className="pr-6">Precision</th><th className="pr-6">Recall</th><th className="pr-6">F1</th><th>Test rows</th>
                </tr></thead>
                <tbody className="tabular-nums">
                  {(["awd", "not_awd"] as const).map((k) => (
                    <tr key={k}>
                      <td className="pr-6">{k === "awd" ? "AWD" : "PTR"}</td>
                      <td className="pr-6">{metrics.precision[k].toFixed(3)}</td>
                      <td className="pr-6">{metrics.recall[k].toFixed(3)}</td>
                      <td className="pr-6">{metrics.f1[k].toFixed(3)}</td>
                      <td>{metrics.support[k]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <p className="ui-meta">Confusion matrix (held-out test)</p>
              <table className="mt-1 text-sm tabular-nums">
                <thead><tr className="text-text-secondary"><th className="pr-4" /><th className="pr-4">Predicted PTR</th><th>Predicted AWD</th></tr></thead>
                <tbody>
                  <tr><td className="pr-4 text-text-secondary">Actual PTR</td><td className="pr-4">{metrics.confusion_matrix[0][0]}</td><td>{metrics.confusion_matrix[0][1]}</td></tr>
                  <tr><td className="pr-4 text-text-secondary">Actual AWD</td><td className="pr-4">{metrics.confusion_matrix[1][0]}</td><td>{metrics.confusion_matrix[1][1]}</td></tr>
                </tbody>
              </table>
            </div>
            <details className="text-sm">
              <summary className="cursor-pointer">Data source and limitations</summary>
              <p className="mt-2 text-xs">Labels: {metrics.target}. Split: {metrics.split_strategy}.</p>
              <a className="text-xs underline" href={metrics.source_url} target="_blank" rel="noreferrer">
                microsoft/rice-irrigation-mapping-s1s2{metrics.source_file ? ` · ${metrics.source_file}` : ""}
              </a>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">{metrics.limitations.map((s) => <li key={s}>{s}</li>)}</ul>
            </details>
          </section>
        )}
      </>}
    </main>
  );
}
