"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { JobStatusOut } from "@/types/api";

/**
 * Polls a background-job status endpoint (signal-runs, ai/train) until it
 * settles. Both endpoints return the same {job_id, job_type, status,
 * result, error, created_at, finished_at} shape (backend/schemas/signal.py's
 * JobStatusOut, reused verbatim for ai/train jobs — see backend/routers/ai.py's
 * get_train_job, which returns the raw job row with an identical shape).
 *
 * First job-polling consumer in this frontend — Signal Analytics and AI
 * Validation both hand a job_id here after their submit mutation returns 202.
 */
export function useJobPoll(path: string | null) {
  return useQuery({
    queryKey: ["job-poll", path],
    queryFn: () => apiFetch<JobStatusOut>(path as string),
    enabled: path !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "error" ? false : 1500;
    },
  });
}
