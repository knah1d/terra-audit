"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { CarbonResult, CreditHistoryEntry } from "@/types/api";

export function useCreditHistory(fieldId: string) {
  return useQuery({
    queryKey: ["credit-history", fieldId],
    queryFn: () => apiFetch<CreditHistoryEntry[]>(`/fields/${fieldId}/credit-history`),
    staleTime: 0, // should reflect a just-run calculation immediately
  });
}

// Preview-only — the matching POST /carbon-credits/commit write path is
// retired for every field_type (see src.persistence.database.
// commit_carbon_credit_result's docstring: a client-supplied, un-frozen
// area_ha could otherwise determine recorded credits). Use the
// evidence-linked Calculations workflow (frontend/hooks/use-calculations.ts,
// if present, or POST /fields/{id}/calculations) to persist a real result.
export function usePreviewCarbonCredits(fieldId: string) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<CarbonResult>(`/fields/${fieldId}/carbon-credits/preview`, { method: "POST", json: body }),
  });
}
