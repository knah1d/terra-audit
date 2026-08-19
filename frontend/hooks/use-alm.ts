"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { CompletenessOut, PracticeScheduleOut } from "@/types/api";

interface SocMeasurementsOut {
  project_t_start: number[];
  project_t_final: number[];
  control_t_start: number[];
  control_t_final: number[];
}

export function useSocMeasurements(fieldId: string) {
  return useQuery({
    queryKey: ["alm-soc-measurements", fieldId],
    queryFn: () => apiFetch<SocMeasurementsOut>(`/fields/${fieldId}/soc-measurements`),
  });
}

export function usePracticeSchedule(fieldId: string) {
  return useQuery({
    queryKey: ["alm-practice-schedule", fieldId],
    queryFn: () => apiFetch<PracticeScheduleOut>(`/fields/${fieldId}/practice-schedule`),
  });
}

export function useAlmCompleteness(fieldId: string) {
  return useQuery({
    queryKey: ["alm-completeness", fieldId],
    queryFn: () => apiFetch<CompletenessOut>(`/fields/${fieldId}/completeness`),
  });
}
