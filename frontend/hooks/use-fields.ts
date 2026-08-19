"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { FieldCreateForm } from "@/lib/schemas/field";
import type { FieldDetailOut, FieldOut } from "@/types/api";

export function useFields() {
  return useQuery({
    queryKey: ["fields"],
    queryFn: () => apiFetch<FieldOut[]>("/fields"),
  });
}

export function useField(fieldId: string, initialData?: FieldDetailOut) {
  return useQuery({
    queryKey: ["field", fieldId],
    queryFn: () => apiFetch<FieldDetailOut>(`/fields/${fieldId}`),
    initialData,
  });
}

export function useCreateField() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: FieldCreateForm & { feature: GeoJSON.Feature }) =>
      apiFetch<FieldDetailOut>("/fields", { method: "POST", json: body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fields"] });
    },
  });
}

export function useUpdateField(fieldId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; district: string }) =>
      apiFetch<FieldDetailOut>(`/fields/${fieldId}`, { method: "PATCH", json: body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fields"] });
      queryClient.invalidateQueries({ queryKey: ["field", fieldId] });
    },
  });
}

export function useDeleteField() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fieldId: string) => apiFetch<void>(`/fields/${fieldId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fields"] });
    },
  });
}
