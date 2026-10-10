"use client";

import { BrainCircuit, Database, Play } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { AwdModelPerformance, type ResearchMetrics } from "@/components/ai/AwdModelPerformance";
import { ConfusionMatrixHeatmap } from "@/components/ai/ConfusionMatrixHeatmap";
import { FeatureImportanceBar } from "@/components/ai/FeatureImportanceBar";
import { RocCurveChart } from "@/components/ai/RocCurveChart";
import { Alert } from "@/components/ui/Alert";
import { useToast } from "@/components/ui/Toast";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { RoleGate } from "@/components/ui/RoleGate";
import { useBuildDataset, useModelValidation, useTrainModel } from "@/hooks/use-ai";
import { apiFetch } from "@/lib/api";
import { useJobPoll } from "@/hooks/use-job-poll";
import type { AiTrainResult } from "@/types/api";

const MODEL_OPTIONS: Array<{ key: "random_forest" | "xgboost"; label: string }> = [
  { key: "random_forest", label: "Random Forest" },
  { key: "xgboost", label: "XGBoost" },
];

function ModelSection({ modelKey, label }: { modelKey: "random_forest" | "xgboost"; label: string }) {
  const train = useTrainModel();
  const toast = useToast();
  const [jobId, setJobId] = useState<string | null>(null);
  const jobPoll = useJobPoll(jobId ? `/ai/train/${jobId}` : null);
  const validation = useModelValidation(modelKey);

  const jobResult = jobId && jobPoll.data?.status === "done" ? (jobPoll.data.result as unknown as AiTrainResult) : null;
  const result = jobResult ?? validation.data ?? null;
  // Stops spinning on any settled state, including a cancelled job or a failed status check.
  const training = train.isPending || (jobId !== null && !jobPoll.isError
    && !["done", "error", "cancelled"].includes(jobPoll.data?.status ?? ""));
  const jobError = jobId && jobPoll.data?.status === "error" ? jobPoll.data.error : null;

  async function handleTrain() {
    setJobId(null);
    try {
      const accepted = await train.mutateAsync({ model_key: modelKey, k: 3 });
      setJobId(accepted.job_id);
      toast.info(`${label} training started`);
    } catch (e) {
      toast.error(e, `Couldn't start ${label} training`);
    }
  }

  return (
    <div className="ui-card flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="ui-subsection-title">{label}</h3>
        <RoleGate allow={["admin", "analyst"]}>
          <Button size="sm" icon={Play} loading={training} onClick={handleTrain}>
            Train &amp; Save
          </Button>
        </RoleGate>
      </div>

      {jobError && <Alert tone="danger" title="Training failed">{jobError}</Alert>}
      {jobPoll.isError && <Alert tone="danger" title="Could not check the training status">{jobPoll.error.message}</Alert>}
      {!result && !training && (
        <p className="text-sm text-text-tertiary">Not trained yet in this session.</p>
      )}

      {result && (
        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-sm">
            <div>
              <p className="ui-meta uppercase tracking-wide">Threshold agreement</p>
              <p className="font-mono text-lg tabular-nums text-text-primary">
                {(result.summary.threshold_agreement_score * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="ui-meta uppercase tracking-wide">Macro F1</p>
              <p className="font-mono text-lg tabular-nums text-text-primary">{result.summary.macro_avg.f1.toFixed(3)}</p>
            </div>
            <div>
              <p className="ui-meta uppercase tracking-wide">CV folds</p>
              <p className="font-mono text-lg tabular-nums text-text-primary">{result.summary.k_used}</p>
            </div>
            <div>
              <p className="ui-meta uppercase tracking-wide">Stratified</p>
              <p className="font-mono text-lg tabular-nums text-text-primary">{result.summary.stratified ? "Yes" : "No"}</p>
            </div>
          </div>
          {!result.summary.stratified && (result.summary.split_strategy === "field_grouped" ? (
            <p className="ui-meta">Entire fields are held out together.</p>
          ) : (
            <Alert tone="warning">Legacy evaluation: rebuild and retrain to use field-grouped evaluation.</Alert>
          ))}

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
  const toast = useToast();
  const awdModel = useQuery({
    queryKey: ["awd-model-metrics"],
    queryFn: () => apiFetch<{ research_benchmark: ResearchMetrics | null }>("/ai/awd-model/metrics"),
  });

  return (
    <div className="ui-container flex flex-col gap-6">
      <PageHeader
        title="AI Validation"
        subtitle="Cross-validate the Random Forest / XGBoost detectors against the Threshold Gate's own labels. Metrics show agreement with the gate, not independent field accuracy."
      />

      {awdModel.error && <Alert tone="danger" title="Could not load the AWD model metrics">{awdModel.error.message}</Alert>}
      {awdModel.data && (awdModel.data.research_benchmark
        ? <AwdModelPerformance metrics={awdModel.data.research_benchmark} />
        : <p className="ui-secondary">No trained AWD practice model is installed on this server.</p>)}

      <RoleGate allow={["admin", "analyst"]}>
        <div className="ui-card flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Database className="size-4 text-brand-600" />
            <span className="ui-secondary">
              Build the labeled training dataset from cached field timeseries before training either model.
            </span>
          </div>
          <Button variant="secondary" size="sm" loading={buildDataset.isPending} onClick={() => buildDataset.mutate(undefined, {
            onSuccess: (d) => toast.success("Dataset built", { description: `${d.row_count} rows across ${d.field_window_groups} field/window groups` }),
            onError: (e) => toast.error(e, "Couldn't build the dataset"),
          })}>
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
