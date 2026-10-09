"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { CurrentProject, FieldWorkflow } from "@/types/api";

/** Step statuses derived from saved records (backend/routers/workflow.py). */
export function useFieldWorkflow(fieldId: string) {
  return useQuery({
    queryKey: ["field-workflow", fieldId],
    queryFn: () => apiFetch<FieldWorkflow>(`/fields/${encodeURIComponent(fieldId)}/workflow-status`),
  });
}

export function useProjectWorkflow(projectId: string) {
  return useQuery({
    queryKey: ["project-workflow", projectId],
    queryFn: () => apiFetch<Array<FieldWorkflow & { name: string; field_type: string; district: string }>>(
      `/projects/${encodeURIComponent(projectId)}/workflow-status`),
  });
}

export type DashboardItem = {
  field_id: string;
  name: string;
  last_activity: { kind: "calculation" | "crop_season" | "signal_run"; at: string };
  project: CurrentProject | null;
  next_step: FieldWorkflow["next_step"];
  needs_attention: Array<{ step: string; status: string; detail: string }>;
};

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => apiFetch<{ recent: DashboardItem[] }>("/dashboard/summary"),
  });
}
