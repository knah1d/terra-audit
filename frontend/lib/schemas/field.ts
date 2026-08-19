import { z } from "zod";

// Mirrors backend/schemas/fields.py — field_type is one of the two
// registry.py keys, chosen once at registration and never editable after.
export const FIELD_TYPE_OPTIONS = [
  { value: "rice_awd", label: "Rice — Alternate Wetting & Drying (VM0051)" },
  { value: "cropland_alm_vm0042", label: "Cropland — Improved Agricultural Land Management (VM0042)" },
] as const;

export const fieldCreateSchema = z.object({
  field_id: z.string().min(1, "Field ID is required"),
  name: z.string().min(1, "Name is required"),
  district: z.string().min(1, "District is required"),
  field_type: z.enum(["rice_awd", "cropland_alm_vm0042"]),
});

export type FieldCreateForm = z.infer<typeof fieldCreateSchema>;

export const fieldUpdateSchema = z.object({
  name: z.string().min(1, "Name is required"),
  district: z.string().min(1, "District is required"),
});

export type FieldUpdateForm = z.infer<typeof fieldUpdateSchema>;

export const coordinatePasteSchema = z.object({
  text: z.string().min(1, "Paste at least 3 lat, lon pairs"),
});
