"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  SocEvidenceCellOut,
  SoilCustodyEventOut,
  SoilLabResultOut,
  SoilSampleOut,
  SoilSamplingPlanOut,
  SoilStratumOut,
} from "@/types/api";

export function useSoilPlans(fieldId: string) {
  return useQuery({
    queryKey: ["soil-plans", fieldId],
    queryFn: () => apiFetch<SoilSamplingPlanOut[]>(`/fields/${fieldId}/soil-sampling-plans`),
  });
}

export function useSoilStrata(fieldId: string, planId: string) {
  return useQuery({
    queryKey: ["soil-strata", fieldId, planId],
    queryFn: () => apiFetch<SoilStratumOut[]>(`/fields/${fieldId}/soil-sampling-plans/${planId}/strata`),
    enabled: !!planId,
  });
}

export function useSoilSamples(fieldId: string, planId: string) {
  return useQuery({
    queryKey: ["soil-samples", fieldId, planId],
    queryFn: () => apiFetch<SoilSampleOut[]>(`/fields/${fieldId}/soil-sampling-plans/${planId}/samples`),
    enabled: !!planId,
  });
}

export function useLabResults(fieldId: string, sampleId: string) {
  return useQuery({
    queryKey: ["soil-lab-results", fieldId, sampleId],
    queryFn: () => apiFetch<SoilLabResultOut[]>(`/fields/${fieldId}/soil-samples/${sampleId}/lab-results`),
    enabled: !!sampleId,
  });
}

export function useCustodyEvents(fieldId: string, sampleId: string) {
  return useQuery({
    queryKey: ["soil-custody-events", fieldId, sampleId],
    queryFn: () => apiFetch<SoilCustodyEventOut[]>(`/fields/${fieldId}/soil-samples/${sampleId}/custody-events`),
    enabled: !!sampleId,
  });
}

export function useSocEvidence(fieldId: string) {
  return useQuery({
    queryKey: ["soc-evidence", fieldId],
    queryFn: () => apiFetch<Record<string, SocEvidenceCellOut>>(`/fields/${fieldId}/soc-evidence`),
  });
}

export function useCreatePlan(fieldId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description: string; measurement_method: string; remeasurement_interval_years: number | null }) =>
      apiFetch<SoilSamplingPlanOut>(`/fields/${fieldId}/soil-sampling-plans`, { method: "POST", json: body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["soil-plans", fieldId] }),
  });
}

export function useCreateStratum(fieldId: string, planId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description: string; area_ha: number | null }) =>
      apiFetch<SoilStratumOut>(`/fields/${fieldId}/soil-sampling-plans/${planId}/strata`, { method: "POST", json: body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["soil-strata", fieldId, planId] }),
  });
}

export function useCreateSample(fieldId: string, planId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<SoilSampleOut>(`/fields/${fieldId}/soil-sampling-plans/${planId}/samples`, { method: "POST", json: body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["soil-samples", fieldId, planId] });
      queryClient.invalidateQueries({ queryKey: ["soc-evidence", fieldId] });
    },
  });
}

export function useCreateLabResult(fieldId: string, sampleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<SoilLabResultOut>(`/fields/${fieldId}/soil-samples/${sampleId}/lab-results`, { method: "POST", json: body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["soil-lab-results", fieldId, sampleId] }),
  });
}

export function useCreateCustodyEvent(fieldId: string, sampleId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<SoilCustodyEventOut>(`/fields/${fieldId}/soil-samples/${sampleId}/custody-events`, { method: "POST", json: body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["soil-custody-events", fieldId, sampleId] }),
  });
}

export function useCreateSocEvidenceReview(fieldId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { site_type: string; timepoint: string; sample_ids: string[]; status: string; reason: string }) =>
      apiFetch(`/fields/${fieldId}/soc-evidence/reviews`, { method: "POST", json: body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["soc-evidence", fieldId] });
      queryClient.invalidateQueries({ queryKey: ["alm-completeness", fieldId] });
    },
  });
}
