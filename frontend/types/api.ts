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

// --- Signal Analytics (mirrors backend/schemas/signal.py) --------------

export type SignalDetector = "threshold" | "random_forest" | "xgboost";

export interface SignalRunRequest {
  window_start: string;
  window_end: string;
  detector: SignalDetector;
  force_refresh: boolean;
}

export interface SignalResult {
  field_id: string;
  cache_source: string;
  total_awd: number;
  sowing_date: string;
  harvest_date: string;
  season_length_days: number;
  from_phenology: boolean;
  detector_used: string;
  model_fallback_msg: string | null;
  n_observations: number;
  vv_mean: number;
  vv_std: number;
  awd_dates: string[];
  window_start: string;
  window_end: string;
  area_ha: number;
  timeseries: Array<Record<string, unknown>>;
}

export interface JobStatusOut {
  job_id: string;
  job_type: string;
  status: "pending" | "running" | "done" | "error";
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string | null;
  finished_at: string | null;
}

export interface SignalRunAccepted {
  job_id: string;
}

// --- Livestock schedule (mirrors backend/schemas/alm.py) ---------------

export type LivestockScenario = "baseline" | "project";
export type ProductivitySystem = "low" | "high";

export interface LivestockEntry {
  livestock_type: string;
  population_head: number;
  productivity_system: ProductivitySystem;
}

export interface LivestockScheduleOut {
  baseline: LivestockEntry[];
  project: LivestockEntry[];
}

// --- Portfolio (mirrors src/database.py's get_portfolio_summary dict) --

export interface PortfolioEntry {
  field_id: string;
  name: string;
  district: string;
  field_type: FieldType;
  area_ha: number | null;
  final_issuance: number | null;
  calculated_at: string | null;
}

// --- AI Validation (mirrors src/ai/evaluate.py's shapes) ---------------

export interface AiDatasetBuildResult {
  row_count: number;
  field_window_groups: number;
  label_counts: Record<string, number>;
}

export interface AiDatasetInfo {
  row_count: number;
  columns: string[];
}

export interface AiTrainAccepted {
  job_id: string;
}

export interface AiPerClassMetric {
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

export interface AiTrainSummary {
  model_name: string;
  k_used: number;
  stratified: boolean;
  threshold_agreement_score: number;
  macro_avg: { precision: number; recall: number; f1: number };
  per_class: Record<string, AiPerClassMetric>;
  confusion_matrix: { labels: string[]; matrix: number[][] };
}

export type AiFeatureImportance = Record<string, number>;

export type AiRocCurveData = Record<string, { fpr: number[]; tpr: number[]; auc: number | null }>;

export interface AiTrainResult {
  summary: AiTrainSummary;
  feature_importance: AiFeatureImportance;
  roc_curve: AiRocCurveData;
}

// --- Team management (mirrors backend/schemas/team.py) -----------------

export type UserRole = "admin" | "analyst" | "viewer";

export interface TeamUserOut {
  user_id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}
