"use client";

/** Held-out performance of the AWD-vs-PTR model trained on Microsoft's
 * rice-irrigation-mapping dataset — shown once, on the AI Validation page,
 * not inside each field. */

type PerClass = { not_awd: number; awd: number };
export type ResearchMetrics = {
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
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export function AwdModelPerformance({ metrics }: { metrics: ResearchMetrics }) {
  return (
    <section className="ui-card space-y-3">
      <h3 className="ui-subsection-title">AWD practice model (Sentinel-1 · Microsoft dataset)</h3>
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
  );
}
