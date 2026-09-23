"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface FieldSeasonRow {
  field_id: string; field_name: string; district: string;
  season_id: string; season_name: string; crops: string[];
  latest_run_status: string | null; latest_run_source: string | null; latest_run_at: string | null;
  open_issue_count: number; open_issue_types: string[];
}

export interface MonitoringDashboard {
  field_season_count: number;
  fields: FieldSeasonRow[];
  coverage_summary: { ready: number; total: number; insufficient_or_missing: number };
  batches: BatchRow[];
  open_issue_count: number;
}

export interface BatchRow {
  batch_id: string; project_id: string | null; batch_type: string; status: string;
  total_children: number; created_by: string; created_at: string;
}

export interface BatchProgress {
  batch: BatchRow;
  total: number;
  by_status: Record<string, number>;
  children: Array<{ job_id: string; job_type: string; status: string; error: string | null; result: unknown }>;
}

export interface IssueRow {
  issue_id: string; field_id: string; season_id: string; issue_type: string; severity: string;
  description: string; status: string; occurrence_count: number;
  first_detected_at: string; last_detected_at: string;
}

export function useMonitoringDashboard(projectId: string) {
  return useQuery({
    queryKey: ["monitoring-dashboard", projectId],
    queryFn: () => apiFetch<MonitoringDashboard>(`/projects/${projectId}/monitoring/dashboard`),
    refetchInterval: 5000,
  });
}

export function useProjectIssues(projectId: string, statusFilter?: string) {
  return useQuery({
    queryKey: ["project-issues", projectId, statusFilter],
    queryFn: () => apiFetch<IssueRow[]>(`/projects/${projectId}/monitoring/issues${statusFilter ? `?status_filter=${statusFilter}` : ""}`),
  });
}

export function useAcknowledgeIssue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ issueId, reason }: { issueId: string; reason?: string }) =>
      apiFetch(`/issues/${issueId}/acknowledge`, { method: "POST", json: { reason } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-issues"] }),
  });
}

export function useResolveIssue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ issueId, reason }: { issueId: string; reason: string }) =>
      apiFetch(`/issues/${issueId}/resolve`, { method: "POST", json: { reason } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-issues"] }),
  });
}

export function useBulkRunMonitoring(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { field_seasons: { field_id: string; season_id: string }[]; force_refresh: boolean }) =>
      apiFetch<{ batch_id: string; job_ids: string[] }>(`/projects/${projectId}/monitoring/bulk-run`, {
        method: "POST", json: body,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monitoring-dashboard", projectId] });
    },
  });
}

export function useBatchProgress(batchId: string | null) {
  return useQuery({
    queryKey: ["batch-progress", batchId],
    queryFn: () => apiFetch<BatchProgress>(`/batches/${batchId}`),
    enabled: !!batchId,
    refetchInterval: (query) => {
      const status = query.state.data?.batch.status;
      return status === "running" ? 2000 : false;
    },
  });
}

export function useCancelBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) => apiFetch<{ cancelled_job_ids: string[] }>(`/batches/${batchId}/cancel`, { method: "POST" }),
    onSuccess: (_d, batchId) => {
      queryClient.invalidateQueries({ queryKey: ["batch-progress", batchId] });
      queryClient.invalidateQueries({ queryKey: ["monitoring-dashboard"] });
    },
  });
}

export function useRetryFailed() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (batchId: string) => apiFetch<{ new_job_ids: string[] }>(`/batches/${batchId}/retry-failed`, { method: "POST", json: {} }),
    onSuccess: (_d, batchId) => {
      queryClient.invalidateQueries({ queryKey: ["batch-progress", batchId] });
      queryClient.invalidateQueries({ queryKey: ["monitoring-dashboard"] });
    },
  });
}

export interface QueueStatus {
  by_status: Record<string, number>;
  by_type: Array<{ job_type: string; status: string; n: number }>;
  oldest_pending_since: string | null;
  workers: Array<{ worker_id: string; hostname: string; started_at: string; last_heartbeat_at: string; stopped_at: string | null }>;
}

export function useQueueStatus() {
  return useQuery({
    queryKey: ["queue-status"],
    queryFn: () => apiFetch<QueueStatus>("/admin/queue-status"),
    refetchInterval: 10000,
  });
}
