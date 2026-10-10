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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["org-summary"] });
    },
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

// Everything that shows which project a field is in, or the project's fields.
function invalidateMembership(queryClient: ReturnType<typeof useQueryClient>, projectId: string | undefined) {
  for (const key of [["project-fields", projectId], ["fields"], ["field-workflow"], ["project-workflow", projectId],
    ["project-eligible-area", projectId], ["monitoring-dashboard", projectId], ["project-mrv", projectId], ["dashboard-summary"]]) {
    void queryClient.invalidateQueries({ queryKey: key });
  }
}

export function useAssignFieldToProject(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { field_id: string; effective_start_date?: string }) =>
      apiFetch<FieldMembershipRow>(`/projects/${projectId}/fields`, { method: "POST", json: body }),
    onSuccess: () => invalidateMembership(queryClient, projectId),
  });
}

export function useEndFieldMembership(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ membershipId, reason, end }: { membershipId: string; reason: string; end: string }) =>
      apiFetch<FieldMembershipRow>(`/projects/${projectId}/fields/${membershipId}/end`, {
        method: "POST", json: { reason, effective_end_date: end },
      }),
    onSuccess: () => invalidateMembership(queryClient, projectId),
  });
}

export function useChangeFieldMembershipStart(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ membershipId, start }: { membershipId: string; start: string }) =>
      apiFetch<FieldMembershipRow>(`/projects/${projectId}/fields/${membershipId}`, {
        method: "PATCH", json: { effective_start_date: start },
      }),
    onSuccess: () => invalidateMembership(queryClient, projectId),
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

/** Organisation-wide counts (not limited to the caller's projects) — an
 * organisation with no fields and no projects gets the Get Started screen. */
export function useOrgSummary() {
  return useQuery({
    queryKey: ["org-summary"],
    queryFn: () => apiFetch<{ field_count: number; project_count: number; is_new_organization: boolean }>("/org/summary"),
  });
}
