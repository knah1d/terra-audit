"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  FindingCommentOut, FindingOut, NotificationOut, ReviewSubmissionOut,
  SubmissionDetailOut, SubmissionDiffOut,
} from "@/types/api";

export function useProjectSubmissions(projectId: string, filters?: { status?: string; reviewerId?: string }) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status_filter", filters.status);
  if (filters?.reviewerId) params.set("reviewer_id", filters.reviewerId);
  const qs = params.toString();
  return useQuery({
    queryKey: ["project-submissions", projectId, filters],
    queryFn: () => apiFetch<ReviewSubmissionOut[]>(`/projects/${projectId}/submissions${qs ? `?${qs}` : ""}`),
    enabled: !!projectId,
  });
}

export function useMyReviews() {
  return useQuery({
    queryKey: ["my-reviews"],
    queryFn: () => apiFetch<ReviewSubmissionOut[]>("/reviews/my"),
  });
}

export function useSubmissionDetail(submissionId: string | null) {
  return useQuery({
    queryKey: ["submission-detail", submissionId],
    queryFn: () => apiFetch<SubmissionDetailOut>(`/submissions/${submissionId}`),
    enabled: !!submissionId,
  });
}

export function useSubmissionDiff(submissionId: string | null, hasPrevious: boolean) {
  return useQuery({
    queryKey: ["submission-diff", submissionId],
    queryFn: () => apiFetch<SubmissionDiffOut>(`/submissions/${submissionId}/diff`),
    enabled: !!submissionId && hasPrevious,
  });
}

export function useCreateSubmission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { project_id: string; calculation_id: string; previous_submission_id?: string }) =>
      apiFetch<ReviewSubmissionOut>(`/projects/${body.project_id}/submissions`, { method: "POST", json: body }),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ["project-submissions", vars.project_id] });
      queryClient.invalidateQueries({ queryKey: ["my-reviews"] });
    },
  });
}

function invalidateSubmission(queryClient: ReturnType<typeof useQueryClient>, submissionId: string, projectId?: string) {
  queryClient.invalidateQueries({ queryKey: ["submission-detail", submissionId] });
  queryClient.invalidateQueries({ queryKey: ["my-reviews"] });
  if (projectId) queryClient.invalidateQueries({ queryKey: ["project-submissions", projectId] });
}

export function useAssignReviewer(submissionId: string, projectId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { reviewer_id: string | null; reason: string }) =>
      apiFetch<ReviewSubmissionOut>(`/submissions/${submissionId}/assign-reviewer`, { method: "POST", json: body }),
    onSuccess: () => invalidateSubmission(queryClient, submissionId, projectId),
  });
}

export function useTransitionSubmission(submissionId: string, projectId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { if_version: number; to_status: string; reason?: string | null }) =>
      apiFetch<ReviewSubmissionOut>(`/submissions/${submissionId}/transition`, { method: "POST", json: body }),
    onSuccess: () => invalidateSubmission(queryClient, submissionId, projectId),
  });
}

export function useCreateFinding(submissionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<FindingOut>(`/submissions/${submissionId}/findings`, { method: "POST", json: body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["submission-detail", submissionId] }),
  });
}

export function useCloseFinding(submissionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ findingId, reason }: { findingId: string; reason: string }) =>
      apiFetch<FindingOut>(`/findings/${findingId}/close`, { method: "POST", json: { reason } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["submission-detail", submissionId] }),
  });
}

export function useFindingComments(findingId: string | null) {
  return useQuery({
    queryKey: ["finding-comments", findingId],
    queryFn: () => apiFetch<FindingCommentOut[]>(`/findings/${findingId}/comments`),
    enabled: !!findingId,
  });
}

export function useAddComment(findingId: string, submissionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { body: string; is_proposed_resolution: boolean }) =>
      apiFetch<FindingCommentOut>(`/findings/${findingId}/comments`, { method: "POST", json: body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["finding-comments", findingId] });
      queryClient.invalidateQueries({ queryKey: ["submission-detail", submissionId] });
    },
  });
}

export function useNotifications(unreadOnly = false) {
  return useQuery({
    queryKey: ["notifications", unreadOnly],
    queryFn: () => apiFetch<NotificationOut[]>(`/notifications${unreadOnly ? "?unread_only=true" : ""}`),
    refetchInterval: 30000,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (notificationId: string) => apiFetch(`/notifications/${notificationId}/read`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
}
