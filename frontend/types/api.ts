// Hand-written types mirroring backend/schemas/*.py response shapes.
// No generated OpenAPI client yet (per the plan's explicit "what not to
// build" — revisit only if the API surface grows enough to justify it).

export type FieldType = "rice_awd" | "cropland_alm_vm0042";

export interface FieldOut {
  field_id: string;
  name: string;
  district: string;
  area_ha: number | null;
  field_type: FieldType;
  created_at: string | null;
}

export interface FieldDetailOut extends FieldOut {
  geojson_geometry: GeoJSON.FeatureCollection;
  alm_cumulative_delta_co2_wp: number | null;
}

export interface GeometryParseResponse {
  feature: GeoJSON.Feature | null;
  error: string | null;
}

// Passthrough of CarbonAssetEngine/AlmCarbonEngine's result dict — only
// the fields the frontend's own logic branches on are named; everything
// else the engine returns rides through as extra properties (matching
// the backend's own CarbonResultOut extra="allow" contract).
export interface CarbonResult {
  final_issuance: number | null;
  qa3_pathway_valid?: boolean | null;
  production_decline_leakage_blocked?: boolean | null;
  cumulative_delta_co2_wp?: number | null;
  qa3_block_reason?: string;
  leakage_block_reason?: string;
  [key: string]: unknown;
}

export interface CommitResponse {
  final_issuance: number | null;
  already_committed: boolean;
}

export interface CreditHistoryEntry {
  calculated_at: string;
  final_issuance: number;
  inputs: Record<string, unknown>;
  result: CarbonResult;
}

export interface PracticeScheduleEntry {
  crop_type?: string | null;
  crop_rotation?: boolean | null;
  cover_crops?: boolean | null;
  intercropping?: boolean | null;
  tillage?: boolean | null;
  tillage_depth_cm?: number | null;
  residue_removed?: boolean | null;
  residue_burned_kg_ha?: number | null;
  synthetic_n_rate_kg_ha?: number | null;
  organic_n_rate_kg_ha?: number | null;
  n_fixing_species?: boolean | null;
  n_fixing_dry_matter_kg_ha?: number | null;
  fuel_use_l_ha?: number | null;
  crop_yield_t_ha?: number | null;
}

export interface PracticeScheduleOut {
  baseline: PracticeScheduleEntry | null;
  project: PracticeScheduleEntry | null;
}

export interface CompletenessOut {
  ready: boolean;
  problems: string[];
}

export interface ApiError {
  detail: string;
}
