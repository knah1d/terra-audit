"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface CropClassification {
  key: string | null;
  common_names: string[];
  alm_eligible: boolean | null;
  vm0051_eligible: boolean | null;
  notes: string | null;
  recognized: boolean;
}

export interface GuidedEnrollment {
  field_type: string;
  accounting_pathway: string | null;
  methodology_bundle: MethodologyBundle | null;
  declared_crops: CropClassification[];
  unsupported_or_partial_scope: {
    requirement_id: string; title: string; implementation_support: string; required_evidence: string;
  }[];
  missing_evidence: string[];
}

export interface MethodologyDocument {
  document_id: string; methodology_key: string; title: string; version: string | null;
  document_type: string; publication_date: string | null; effective_date: string | null;
  superseded_by: string | null; corrects_document_id: string | null; source_url: string | null;
  ingestion_status: "ingested_local" | "referenced_external"; notes: string | null; role?: string;
}

export interface MethodologyBundle {
  bundle_id: string; accounting_pathway: string; bundle_version: string;
  effective_from: string | null; effective_until: string | null; is_current: boolean;
  notes: string | null; documents?: MethodologyDocument[];
}

export function useGuidedEnrollment(fieldId: string) {
  return useQuery({
    queryKey: ["guided-enrollment", fieldId],
    queryFn: () => apiFetch<GuidedEnrollment>(`/fields/${fieldId}/guided-enrollment`),
  });
}

export interface QuantificationUnit {
  unit_id: string; field_id: string; name: string; area_ha: number;
  eligibility_status: "eligible" | "excluded" | "needs_review"; exclusion_reason: string | null;
  created_by: string; created_at: string;
}

export function useQuantificationUnits(fieldId: string) {
  return useQuery({
    queryKey: ["quantification-units", fieldId],
    queryFn: () => apiFetch<QuantificationUnit[]>(`/fields/${fieldId}/quantification-units`),
  });
}

export function useCreateQuantificationUnit(fieldId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; area_ha: number; eligibility_status: string; exclusion_reason?: string }) =>
      apiFetch<QuantificationUnit>(`/fields/${fieldId}/quantification-units`, { method: "POST", json: body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["quantification-units", fieldId] }),
  });
}

export function useMethodologyBundles(accountingPathway?: string) {
  return useQuery({
    queryKey: ["methodology-bundles", accountingPathway],
    queryFn: () => apiFetch<MethodologyBundle[]>(`/methodology/bundles${accountingPathway ? `?accounting_pathway=${accountingPathway}` : ""}`),
  });
}

export function useProjectApplicability(projectId: string, accountingPathway: string | undefined) {
  return useQuery({
    queryKey: ["project-applicability", projectId, accountingPathway],
    queryFn: () => apiFetch<{ explicit_decision: unknown; resolved_bundle: MethodologyBundle | null }>(
      `/projects/${projectId}/methodology-applicability?accounting_pathway=${accountingPathway}`,
    ),
    enabled: !!accountingPathway,
  });
}

export function useSetProjectApplicability(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { accounting_pathway: string; bundle_id: string; reason: string }) =>
      apiFetch(`/projects/${projectId}/methodology-applicability`, { method: "POST", json: body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-applicability", projectId] }),
  });
}

export interface EligibleArea {
  field_count: number; totals_ha: Record<string, number>;
  fields_without_quantification_units: string[]; note: string;
}

export function useProjectEligibleArea(projectId: string) {
  return useQuery({
    queryKey: ["project-eligible-area", projectId],
    queryFn: () => apiFetch<EligibleArea>(`/projects/${projectId}/eligible-area`),
  });
}
