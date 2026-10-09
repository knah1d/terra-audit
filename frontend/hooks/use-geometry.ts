"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { GeometryParseResponse, LandUseResponse } from "@/types/api";

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

/** District detected on the backend from the boundary (detect_district);
 * `district` is null when the boundary lies outside Bangladesh. Accepts a
 * Feature or a stored FeatureCollection. */
export function useDetectedDistrict(geojson: GeoJSON.Feature | GeoJSON.FeatureCollection | null) {
  return useQuery({
    queryKey: ["detect-district", geojson ? JSON.stringify(geojson) : null],
    queryFn: () => apiFetch<{ district: string | null }>("/geometry/district", { method: "POST", json: geojson }),
    enabled: geojson !== null,
  });
}

/** Observed land use ("Field Type") suggested on the backend from ESA
 * WorldCover + Sentinel-1 (src/signals/land_use.py). Errors (503 when Earth
 * Engine isn't configured, 502 when it fails) mean "enter it manually" —
 * no retry, since each attempt is a multi-second Earth Engine call. */
export function useDetectedLandUse(geojson: GeoJSON.Feature | GeoJSON.FeatureCollection | null) {
  return useQuery({
    queryKey: ["detect-land-use", geojson ? JSON.stringify(geojson) : null],
    queryFn: () => apiFetch<LandUseResponse>("/geometry/land-use", { method: "POST", json: geojson }),
    enabled: geojson !== null,
    retry: false,
    staleTime: Infinity,
  });
}
