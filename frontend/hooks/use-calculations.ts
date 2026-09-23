"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { CalculationHistoryRow, CalculationOut, ReadinessCheck } from "@/types/api";

export function useCalculationHistory(fieldId: string) {
  return useQuery({
    queryKey: ["calculations", fieldId],
    queryFn: () => apiFetch<CalculationHistoryRow[]>(`/fields/${fieldId}/calculations?include_legacy=true`),
    staleTime: 0,
  });
}

export function useCalculationChain(calculationId: string | null) {
  return useQuery({
    queryKey: ["calculation-chain", calculationId],
    queryFn: () => apiFetch<CalculationOut[]>(`/calculations/${calculationId}/chain`),
    enabled: !!calculationId,
  });
}

export function useReadiness(fieldId: string) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<{ checklist: ReadinessCheck[]; bundle_id: string | null }>(`/fields/${fieldId}/calculations/readiness`, {
        method: "POST", json: body,
      }),
  });
}

export function usePreviewCalculation(fieldId: string) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<{ result: Record<string, unknown>; readiness: ReadinessCheck[]; bundle_id: string | null }>(
        `/fields/${fieldId}/calculations/preview`, { method: "POST", json: body },
      ),
  });
}

export function useCommitCalculation(fieldId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ body, idempotencyKey }: { body: Record<string, unknown>; idempotencyKey: string }) =>
      apiFetch<{ calculation: CalculationOut; already_committed: boolean }>(
        `/fields/${fieldId}/calculations`,
        { method: "POST", json: body, headers: { "Idempotency-Key": idempotencyKey } },
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["calculations", fieldId] }),
  });
}

export function useRecordDetermination(fieldId: string) {
  return useMutation({
    mutationFn: (body: {
      project_id: string | null; accounting_pathway: string; requirement_id: string;
      monitoring_period_start: string; monitoring_period_end: string; status: string; reason: string;
    }) => apiFetch(`/fields/${fieldId}/calculations/readiness/determinations`, { method: "POST", json: body }),
  });
}
