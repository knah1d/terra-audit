"use client";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export type CropSeasonRow = {
  id: string; season_id: string; version_record_id?: string; created_at: string;
  payload: {
    name: string; crops: string[]; start_date: string; end_date: string; notes: string;
    version?: number; season_type?: string; is_historical?: boolean;
    fallow_reason?: string; missing_period_reason?: string; intercrop_arrangement?: string;
    crop_sequence?: { crop: string; start_date: string; end_date: string }[];
  };
};
/** Current payload and stable season ID; immutable history has its own endpoint. */
export function useCropSeasons(fieldId: string) {
  return useQuery({
    queryKey: ["crop-seasons", fieldId, "current"],
    queryFn: () => apiFetch<CropSeasonRow[]>(`/fields/${encodeURIComponent(fieldId)}/crop-seasons?current_only=true`),
  });
}
