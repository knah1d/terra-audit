import { z } from "zod";

// Mirrors backend/schemas/carbon.py CarbonCalcRequestRice (which itself
// mirrors CarbonAssetEngine.calculate_credits()'s keyword args exactly).
export const AMENDMENT_TYPE_OPTIONS = [
  { value: "straw_shortly_before", label: "Straw, incorporated <30 days before cultivation" },
  { value: "straw_long_before", label: "Straw, incorporated >30 days before cultivation" },
  { value: "compost", label: "Compost" },
  { value: "farmyard_manure", label: "Farmyard manure" },
  { value: "green_manure", label: "Green manure" },
] as const;

export const ledgerRiceSchema = z.object({
  season_length_days: z.coerce.number().int().min(1).max(365),
  // No upper bound: VM0051 has no maximum-project-area requirement (the
  // methodology's only size gate is the 60,000 tCO2e/yr QA3 threshold,
  // which calculate_credits() enforces on the *result*, not the input
  // area). The old 500 ha cap was a Streamlit UI default, not a
  // methodology constraint.
  area_ha: z.coerce.number().min(0.1),
  awd_events: z.coerce.number().int().min(0).max(20),
  q_n_kg_per_ha: z.coerce.number().min(0).max(300),
  preseason_category: z.enum(["short", "long"]),
  baseline_amendment_type: z.string(),
  baseline_amendment_rate: z.coerce.number().min(0).max(50),
  project_amendment_type: z.string(),
  project_amendment_rate: z.coerce.number().min(0).max(50),
});

export type LedgerRiceForm = z.infer<typeof ledgerRiceSchema>;

// Mirrors backend/schemas/carbon.py CarbonCalcRequestAlm.
export const ledgerAlmSchema = z.object({
  // No upper bound — VM0042 has no maximum-project-area requirement either
  // (see ledgerRiceSchema's area_ha comment above).
  area_ha: z.coerce.number().min(0.1),
  verification_years: z.coerce.number().min(1.0).max(5.0),
  non_permanence_risk_pct: z.coerce.number().min(0).max(100),
});

export type LedgerAlmForm = z.infer<typeof ledgerAlmSchema>;
