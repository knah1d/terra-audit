"use client";

import { BrainCircuit, Database, Play } from "lucide-react";
import { useState } from "react";
import { ConfusionMatrixHeatmap } from "@/components/ai/ConfusionMatrixHeatmap";
import { FeatureImportanceBar } from "@/components/ai/FeatureImportanceBar";
import { RocCurveChart } from "@/components/ai/RocCurveChart";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { RoleGate } from "@/components/ui/RoleGate";
import { useBuildDataset, useModelValidation, useTrainModel } from "@/hooks/use-ai";
import { useJobPoll } from "@/hooks/use-job-poll";
import type { AiTrainResult } from "@/types/api";

const MODEL_OPTIONS: Array<{ key: "random_forest" | "xgboost"; label: string }> = [
  { key: "random_forest", label: "Random Forest" },
  { key: "xgboost", label: "XGBoost" },
];

function ModelSection({ modelKey, label }: { modelKey: "random_forest" | "xgboost"; label: string }) {
  const train = useTrainModel();
  const [jobId, setJobId] = useState<string | null>(null);
  const jobPoll = useJobPoll(jobId ? `/ai/train/${jobId}` : null);
  const validation = useModelValidation(modelKey);

  const jobResult = jobId && jobPoll.data?.status === "done" ? (jobPoll.data.result as unknown as AiTrainResult) : null;
  const result = jobResult ?? validation.data ?? null;
  const training = train.isPending || (jobId !== null && jobPoll.data?.status !== "done" && jobPoll.data?.status !== "error");
  const jobError = jobId && jobPoll.data?.status === "error" ? jobPoll.data.error : null;

  async function handleTrain() {
    setJobId(null);
    const accepted = await train.mutateAsync({ model_key: modelKey, k: 3 });
    setJobId(accepted.job_id);
  }

  return (
    <div className="surface-card flex flex-col gap-4 rounded-xl p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-text-primary">{label}</h3>
        <RoleGate allow={["admin", "analyst"]}>
          <Button size="sm" icon={Play} loading={training} onClick={handleTrain}>
            Train &amp; Save
          </Button>
        </RoleGate>
      </div>

      {jobError && <Alert tone="danger">{jobError}</Alert>}
      {!result && !training && (
        <p className="text-sm text-text-tertiary">Not trained yet in this session.</p>
      )}

      {result && (
        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
            <div>
              <p className="text-xs uppercase tracking-wide text-text-tertiary">Threshold agreement</p>
              <p className="font-mono text-lg tabular-nums text-text-primary">
                {(result.summary.threshold_agreement_score * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-text-tertiary">Macro F1</p>
              <p className="font-mono text-lg tabular-nums text-text-primary">{result.summary.macro_avg.f1.toFixed(3)}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-text-tertiary">CV folds</p>
              <p className="font-mono text-lg tabular-nums text-text-primary">{result.summary.k_used}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-text-tertiary">Stratified</p>
              <p className="font-mono text-lg tabular-nums text-text-primary">{result.summary.stratified ? "Yes" : "No"}</p>
            </div>
          </div>
          {!result.summary.stratified && (
            <Alert tone="warning">
              A class had too few samples to stratify — cross-validation fell back to unstratified folds.
            </Alert>
          )}

          <div>
            <p className="mb-2 text-sm font-medium text-text-primary">Confusion Matrix (predicted vs. threshold-gate label)</p>
            <ConfusionMatrixHeatmap
              labels={result.summary.confusion_matrix.labels}
              matrix={result.summary.confusion_matrix.matrix}
            />
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-text-primary">Feature Importance</p>
            <FeatureImportanceBar importance={result.feature_importance} />
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-text-primary">ROC Curve (one-vs-rest)</p>
            <RocCurveChart roc={result.roc_curve} />
          </div>
        </div>
      )}
    </div>
  );
}

export default function AiValidationPage() {
  const buildDataset = useBuildDataset();

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title="AI Validation"
        subtitle="Cross-validate the Random Forest / XGBoost detectors against the Threshold Gate's own labels."
      />

      <Alert tone="warning" title="Not an independent accuracy check">
        These detectors are trained to reproduce the Threshold Gate&apos;s own output — there is no independent
        ground truth yet. Validation metrics below measure agreement with the gate, not real-world irrigation
        accuracy.
      </Alert>

      <RoleGate allow={["admin", "analyst"]}>
        <div className="surface-card flex items-center justify-between rounded-xl p-4">
          <div className="flex items-center gap-2.5">
            <Database className="size-4 text-brand-600" />
            <span className="text-sm text-text-secondary">
              Build the labeled training dataset from cached field timeseries before training either model.
            </span>
          </div>
          <Button variant="secondary" size="sm" loading={buildDataset.isPending} onClick={() => buildDataset.mutate()}>
            Build / Rebuild Dataset
          </Button>
        </div>
      </RoleGate>

      {buildDataset.data && (
        <Alert tone="success" title="Dataset built">
          {buildDataset.data.row_count} rows across {buildDataset.data.field_window_groups} field/window groups —{" "}
          {Object.entries(buildDataset.data.label_counts).map(([label, count]) => `${label}: ${count}`).join(", ")}
        </Alert>
      )}

      <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
        <BrainCircuit className="size-4 text-brand-600" />
        Model Validation
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {MODEL_OPTIONS.map((m) => (
          <ModelSection key={m.key} modelKey={m.key} label={m.label} />
        ))}
      </div>
    </div>
  );
}
