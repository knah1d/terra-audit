"use client";

import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { SignalResult, SignalRunAccepted, SignalRunRequest } from "@/types/api";

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
