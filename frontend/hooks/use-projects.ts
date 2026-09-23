"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ProjectOut } from "@/types/api";

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: () => apiFetch<ProjectOut[]>("/projects"),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => apiFetch<ProjectOut>("/projects", { method: "POST", json: body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export interface ProjectMemberRow {
  user_id: string;
  email: string;
  project_role: "lead" | "contributor" | "viewer";
  added_at: string | null;
}

export function useProjectMembers(projectId: string | undefined) {
  return useQuery({
    queryKey: ["project-members", projectId],
    queryFn: () => apiFetch<ProjectMemberRow[]>(`/projects/${projectId}/members`),
    enabled: !!projectId,
  });
}

export interface FieldMembershipRow {
  membership_id: string;
  field_id: string;
  effective_start_date: string;
  effective_end_date: string | null;
  removed_at: string | null;
  removed_reason: string | null;
}

export function useProjectFields(projectId: string | undefined) {
  return useQuery({
    queryKey: ["project-fields", projectId],
    queryFn: () => apiFetch<FieldMembershipRow[]>(`/projects/${projectId}/fields`),
    enabled: !!projectId,
  });
}

export function useAssignFieldToProject(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { field_id: string; effective_start_date?: string }) =>
      apiFetch<FieldMembershipRow>(`/projects/${projectId}/fields`, { method: "POST", json: body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-fields", projectId] }),
  });
}

export function useEndFieldMembership(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ membershipId, reason }: { membershipId: string; reason: string }) =>
      apiFetch<FieldMembershipRow>(`/projects/${projectId}/fields/${membershipId}/end`, {
        method: "POST", json: { reason },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-fields", projectId] }),
  });
}

export function useAddProjectMember(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { user_id: string; project_role: string; reason?: string }) =>
      apiFetch<ProjectMemberRow[]>(`/projects/${projectId}/members`, { method: "POST", json: body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-members", projectId] }),
  });
}
