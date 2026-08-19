"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { GeometryParseResponse } from "@/types/api";

export function useParseCoordinates() {
  return useMutation({
    mutationFn: (text: string) =>
      apiFetch<GeometryParseResponse>("/fields/parse/coordinates", { method: "POST", json: { text } }),
  });
}

export function useParseGeojson() {
  return useMutation({
    mutationFn: (content: string) =>
      apiFetch<GeometryParseResponse>("/fields/parse/geojson", { method: "POST", json: { content } }),
  });
}

export function useParseKml() {
  return useMutation({
    mutationFn: (content: string) =>
      apiFetch<GeometryParseResponse>("/fields/parse/kml", { method: "POST", json: { content } }),
  });
}

/** Computed on the backend (compute_area_ha) — cached by feature identity
 * so redrawing the same polygon doesn't refire the request. */
export function useComputedArea(feature: GeoJSON.Feature | null) {
  return useQuery({
    queryKey: ["compute-area", feature ? JSON.stringify(feature.geometry) : null],
    queryFn: () => apiFetch<{ area_ha: number }>("/geometry/area", { method: "POST", json: feature }),
    enabled: feature !== null,
  });
}
