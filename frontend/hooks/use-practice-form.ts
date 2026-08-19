"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { PracticeScheduleEntry, PracticeScheduleOut } from "@/types/api";

export function useSavePracticeSchedule(fieldId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ scenario, practices }: { scenario: "baseline" | "project"; practices: PracticeScheduleEntry }) =>
      apiFetch<PracticeScheduleOut>(`/fields/${fieldId}/practice-schedule/${scenario}`, {
        method: "PUT",
        json: practices,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alm-practice-schedule", fieldId] });
      queryClient.invalidateQueries({ queryKey: ["alm-completeness", fieldId] });
    },
  });
}

export function useSaveSocMeasurements(fieldId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      siteType,
      timepoint,
      values,
    }: {
      siteType: "project" | "control";
      timepoint: "t_start" | "t_final";
      values: number[];
    }) =>
      apiFetch(`/fields/${fieldId}/soc-measurements/${siteType}/${timepoint}`, {
        method: "PUT",
        json: { values },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alm-completeness", fieldId] });
      queryClient.invalidateQueries({ queryKey: ["alm-soc-measurements", fieldId] });
    },
  });
}
