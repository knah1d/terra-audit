"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { CarbonResult, CommitResponse, CreditHistoryEntry } from "@/types/api";

export function useCreditHistory(fieldId: string) {
  return useQuery({
    queryKey: ["credit-history", fieldId],
    queryFn: () => apiFetch<CreditHistoryEntry[]>(`/fields/${fieldId}/credit-history`),
    staleTime: 0, // should reflect a just-run calculation immediately
  });
}

export function usePreviewCarbonCredits(fieldId: string) {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<CarbonResult>(`/fields/${fieldId}/carbon-credits/preview`, { method: "POST", json: body }),
  });
}

export function useCommitCarbonCredits(fieldId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ body, idempotencyKey }: { body: Record<string, unknown>; idempotencyKey: string }) =>
      apiFetch<CommitResponse>(`/fields/${fieldId}/carbon-credits/commit`, {
        method: "POST",
        json: body,
        headers: { "Idempotency-Key": idempotencyKey },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["credit-history", fieldId] });
      queryClient.invalidateQueries({ queryKey: ["field", fieldId] }); // cumulative delta may have changed
    },
  });
}
