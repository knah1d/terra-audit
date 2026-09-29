"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ProductionRecordOut, Vmd0054ResultOut } from "@/types/api";

export function useProductionRecords(fieldId: string) {
  return useQuery({
    queryKey: ["production-records", fieldId],
    queryFn: () => apiFetch<ProductionRecordOut[]>(`/fields/${fieldId}/production-records`),
  });
}

export function useCreateProductionRecord(fieldId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<ProductionRecordOut>(`/fields/${fieldId}/production-records`, { method: "POST", json: body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["production-records", fieldId] }),
  });
}

export function useImportProductionRecords(fieldId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (records: Record<string, unknown>[]) =>
      apiFetch<{ created: string[] }>(`/fields/${fieldId}/production-records/import`, { method: "POST", json: { records } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["production-records", fieldId] }),
  });
}

export function useVmd0054Leakage(fieldId: string) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<Vmd0054ResultOut>(`/fields/${fieldId}/production-records/vmd0054-leakage`, { method: "POST", json: body }),
  });
}

export interface LeakageAssessment {
  assessment_id: string;
  project_id: string;
  bundle_id: string;
  period_start: string;
  period_end: string;
  created_at: string;
  payload: Record<string, unknown>;
}

export function useLeakageAssessments(fieldId: string) {
  return useQuery({
    queryKey: ["leakage-assessments", fieldId],
    queryFn: () => apiFetch<LeakageAssessment[]>(`/fields/${fieldId}/production-records/leakage-assessments`),
  });
}

export function useSaveLeakageAssessment(fieldId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => apiFetch<{ assessment: LeakageAssessment; result: Vmd0054ResultOut }>(
      `/fields/${fieldId}/production-records/leakage-assessments`, { method: "POST", json: body }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["leakage-assessments", fieldId] });
      void client.invalidateQueries({ queryKey: ["calculations", fieldId] });
    },
  });
}
