"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api";
import type { AiDatasetBuildResult, AiDatasetInfo, AiTrainAccepted, AiTrainResult } from "@/types/api";

export function useBuildDataset() {
  return useMutation({
    mutationFn: () => apiFetch<AiDatasetBuildResult>("/ai/dataset/build", { method: "POST" }),
  });
}

export function useDatasetInfo() {
  return useQuery({
    queryKey: ["ai-dataset"],
    queryFn: () => apiFetch<AiDatasetInfo>("/ai/dataset"),
  });
}

export function useTrainModel() {
  return useMutation({
    mutationFn: (body: { model_key: "random_forest" | "xgboost"; k?: number }) =>
      apiFetch<AiTrainAccepted>("/ai/train", { method: "POST", json: body }),
  });
}

/** 404s if the model has never been trained — surfaced as `notFound` rather
 * than a thrown query error, since "not trained yet" is an expected state
 * here, not a failure. */
export function useModelValidation(modelKey: string | null) {
  return useQuery({
    queryKey: ["ai-validate", modelKey],
    queryFn: async () => {
      try {
        return await apiFetch<AiTrainResult>(`/ai/validate/${modelKey}`);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    enabled: modelKey !== null,
  });
}
