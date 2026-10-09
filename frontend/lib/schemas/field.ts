import { z } from "zod";

// Mirrors backend/schemas/fields.py — field_type is one of the two
// registry.py keys, chosen once at registration and never editable after.
export const FIELD_TYPE_OPTIONS = [
  { value: "rice_awd", label: "Rice — Alternate Wetting & Drying (VM0051)" },
  { value: "cropland_alm_vm0042", label: "Cropland — Improved Agricultural Land Management (VM0042)" },
] as const;

// Observed land use ("Field Type") — mirrors src/signals/land_use.py
// LAND_USE_VALUES. "" in the form means "not set" and is sent as null.
export const LAND_USE_OPTIONS = [
  { value: "rice_paddy", label: "Rice paddy" },
  { value: "rice_rotation", label: "Rice in rotation with other crops" },
  { value: "upland_cropland", label: "Upland cropland" },
  { value: "non_cropland", label: "Not cropland" },
] as const;

const landUseField = z.enum(["", "rice_paddy", "rice_rotation", "upland_cropland", "non_cropland"]);

// Methodology a land use points to; rice_rotation and non_cropland suggest
// none (either methodology may apply, or neither).
export const SUGGESTED_METHODOLOGY: Partial<Record<z.infer<typeof landUseField>, FieldCreateForm["field_type"]>> = {
  rice_paddy: "rice_awd",
  upland_cropland: "cropland_alm_vm0042",
};

export function landUseLabel(value: string | null | undefined) {
  return LAND_USE_OPTIONS.find((o) => o.value === value)?.label ?? "Not set";
}

export const fieldCreateSchema = z.object({
  field_id: z.string().min(1, "Field ID is required"),
  name: z.string().min(1, "Name is required"),
  district: z.string().min(1, "District is required"),
  field_type: z.enum(["rice_awd", "cropland_alm_vm0042"]),
  land_use: landUseField,
});

export type FieldCreateForm = z.infer<typeof fieldCreateSchema>;

export const fieldUpdateSchema = z.object({
  name: z.string().min(1, "Name is required"),
  district: z.string().min(1, "District is required"),
  land_use: landUseField,
});

export type FieldUpdateForm = z.infer<typeof fieldUpdateSchema>;

export const coordinatePasteSchema = z.object({
  text: z.string().min(1, "Paste at least 3 lat, lon pairs"),
});
