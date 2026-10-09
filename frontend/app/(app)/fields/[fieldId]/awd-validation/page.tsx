"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Alert } from "@/components/ui/Alert";
import { apiFetch } from "@/lib/api";

type ResearchMetrics = {
  benchmark_version: string;
  source_url: string;
  target: string;
  split_strategy: string;
  accuracy: number;
  balanced_accuracy: number;
  train_rows: number;
  test_rows: number;
  confusion_matrix: number[][];
  f1: { not_awd: number; awd: number };
  limitations: string[];
};
type Comparison = {
  field_id: string;
  experimental: boolean;
  research_benchmark: ResearchMetrics | null;
  existing_signal: {
    window_start: string | null;
    window_end: string | null;
    detector_used: string | null;
    candidate_drydowns: number | null;
    source: string | null;
  } | null;
  field_ml_prediction: null;
  comparison_status: string;
  ground_truth_status: string;
  affects_carbon_calculation: false;
  message: string;
};

export default function ExternalAWDValidationPage() {
  const field = useFieldContext();
  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["external-awd-comparison", field.field_id],
    queryFn: () => apiFetch<Comparison>(
      `/fields/${encodeURIComponent(field.field_id)}/awd-external-comparison`
    ),
  });

  return (
    <main className="ui-container space-y-6">
      <div>
        <h2 className="ui-section-title">AWD research validation</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Experimental research benchmark alongside the existing satellite rule detector.
          Nothing on this page changes carbon calculations, readiness or issuance.
        </p>
      </div>
      {isPending && <Alert tone="info">Loading benchmark and last signal run…</Alert>}
      {error && <Alert tone="danger" title="Unable to load comparison">
        {error.message} <button type="button" className="underline" onClick={() => void refetch()}>Retry</button>
      </Alert>}
      {data && <>
        <Alert tone="warning" title="Experimental, not independent cycle verification">
          {data.message} No field-level model prediction or ground-truth accuracy is claimed.
        </Alert>
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="ui-card space-y-3">
            <h3 className="ui-subsection-title">Current Terra Audit signal</h3>
            {data.existing_signal ? <>
              <p className="text-sm">Detector: <strong>{data.existing_signal.detector_used ?? "Unknown"}</strong></p>
              <p className="text-sm">Candidate drydowns: <strong>{data.existing_signal.candidate_drydowns ?? "—"}</strong></p>
              <p className="text-sm text-text-secondary">Window: {data.existing_signal.window_start ?? "—"} – {data.existing_signal.window_end ?? "—"}</p>
              <p className="text-xs text-text-tertiary">Source: {data.existing_signal.source ?? "Unknown"}</p>
            </> : <p className="text-sm text-text-secondary">No saved signal run for this field.</p>}
            <Link className="text-sm underline" href={`/fields/${encodeURIComponent(field.field_id)}/signal-analytics`}>Open Signal Analytics</Link>
          </section>
          <section className="ui-card space-y-3">
            <h3 className="ui-subsection-title">Independent research benchmark</h3>
            {data.research_benchmark ? <>
              <p className="text-sm">Task: {data.research_benchmark.target}</p>
              <div className="grid grid-cols-2 gap-3">
                <div><p className="ui-meta">Held-out accuracy</p><p className="text-xl font-semibold tabular-nums">{(data.research_benchmark.accuracy * 100).toFixed(1)}%</p></div>
                <div><p className="ui-meta">AWD F1</p><p className="text-xl font-semibold tabular-nums">{data.research_benchmark.f1.awd.toFixed(3)}</p></div>
              </div>
              <p className="text-xs text-text-secondary">Train/test rows: {data.research_benchmark.train_rows} / {data.research_benchmark.test_rows}</p>
              <p className="text-xs text-text-secondary">Split: {data.research_benchmark.split_strategy}</p>
              <p className="text-xs text-text-secondary">Evaluation dataset: Punjab research features, not Terra Audit field data.</p>
              <details className="text-sm"><summary className="cursor-pointer">Confusion matrix and limitations</summary>
                <p className="mt-2 font-mono text-xs">Rows: actual not-AWD, AWD; columns: predicted not-AWD, AWD</p>
                <pre className="mt-1 overflow-x-auto text-xs">{JSON.stringify(data.research_benchmark.confusion_matrix, null, 2)}</pre>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">{data.research_benchmark.limitations.map(s => <li key={s}>{s}</li>)}</ul>
              </details>
            </> : <>
              <p className="text-sm text-text-secondary">
                No external benchmark metrics installed on this server. Run the offline
                research-data trainer to produce them; no accuracy value is fabricated.
              </p>
              <a className="text-sm underline" href="https://github.com/microsoft/rice-irrigation-mapping-s1s2" target="_blank" rel="noreferrer">Research source</a>
            </>}
          </section>
        </div>
        <section className="ui-card space-y-2">
          <h3 className="ui-subsection-title">Comparison readiness</h3>
          <p className="text-sm"><strong>Field-level ML:</strong> blocked until satellite preprocessing and features are compatible.</p>
          <p className="text-sm"><strong>Ground truth:</strong> unavailable; independent field AWD event validation not established.</p>
          <p className="text-sm"><strong>Carbon calculations:</strong> continue using the existing workflow, unaffected.</p>
        </section>
      </>}
    </main>
  );
}
