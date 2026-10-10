"use client";

import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api";
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
    queryFn: async () => {
      try {
        return await apiFetch<SignalResult>(`/fields/${fieldId}/signal-runs/latest`);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    retry: false,
  });
}

export function useCancelSignalRun(fieldId: string) {
  return useMutation({
    mutationFn: (jobId: string) => apiFetch(`/fields/${fieldId}/signal-runs/${jobId}/cancel`, { method: "POST" }),
  });
}

export function useActiveSignalRuns(fieldId: string) {
  return useQuery({
    queryKey: ["signal-run", "active", fieldId],
    queryFn: () => apiFetch<Array<{ job_id: string; request: SignalRunRequest }>>(`/fields/${fieldId}/signal-runs/active`),
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
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SignalRunRequest) =>
      apiFetch<SignalResult | SignalRunAccepted>(`/fields/${fieldId}/signal-runs`, {
        method: "POST",
        json: body,
      }),
    // A cache hit is saved as a completed run immediately; a queued run is
    // refreshed again when its job finishes (see the Signal Analytics page).
    onSuccess: () => invalidateSignalViews(queryClient, fieldId),
  });
}

/** Everything that shows "the latest/saved signal runs" for this field. */
export function invalidateSignalViews(queryClient: QueryClient, fieldId: string) {
  // A finished run also completes the Signal Analytics step (tab dots, overview, dashboard).
  for (const queryKey of [["signal-run", "latest", fieldId], ["signal-evidence", fieldId], ["external-awd-comparison", fieldId],
    ["field-workflow", fieldId], ["project-workflow"], ["guided-enrollment", fieldId], ["dashboard-summary"]]) {
    void queryClient.invalidateQueries({ queryKey });
  }
}

export function isSignalRunAccepted(body: SignalResult | SignalRunAccepted): body is SignalRunAccepted {
  return "job_id" in body;
}
