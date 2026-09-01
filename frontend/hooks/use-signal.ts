"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { SignalResult, SignalRunAccepted, SignalRunRequest } from "@/types/api";

/**
 * GET /fields/{fieldId}/signal-runs/latest — read-only lookup of the most
 * recently completed signal_run job for this field, independent of
 * whether it was served by the cache-hit fast path or a background job.
 * NOT tied to any specific committed carbon-credit verification (no
 * schema link exists between a credit_history row and the signal_run
 * that produced its rice inputs) — this is "current signal context," the
 * same best-effort role Streamlit's carbon_* session_state keys played.
 * 404s when no run has ever completed for this field; callers should
 * treat that as "nothing to prefill from yet," not an error.
 */
export function useLatestSignalRun(fieldId: string) {
  return useQuery({
    queryKey: ["signal-run", "latest", fieldId],
    queryFn: () => apiFetch<SignalResult>(`/fields/${fieldId}/signal-runs/latest`),
    retry: false,
  });
}

/**
 * POST /fields/{fieldId}/signal-runs is a hybrid endpoint (backend/routers/
 * signal.py): a cache hit returns a SignalResult directly (200), a cache
 * miss or force_refresh schedules a background job and returns
 * SignalRunAccepted (202). apiFetch doesn't special-case status codes, so
 * callers branch on response shape ("job_id" in body) — see
 * SignalAnalyticsPage for the branch.
 */
export function useRunSignalAnalysis(fieldId: string) {
  return useMutation({
    mutationFn: (body: SignalRunRequest) =>
      apiFetch<SignalResult | SignalRunAccepted>(`/fields/${fieldId}/signal-runs`, {
        method: "POST",
        json: body,
      }),
  });
}

export function isSignalRunAccepted(body: SignalResult | SignalRunAccepted): body is SignalRunAccepted {
  return "job_id" in body;
}
