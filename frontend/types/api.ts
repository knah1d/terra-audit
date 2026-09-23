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
  // The real, stable credit_history.id — identifies one committed
  // verification for export/evidence purposes. Never an array index.
  credit_history_id: number;
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
  limestone_applied_t_ha?: number | null;
  dolomite_applied_t_ha?: number | null;
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
  split_strategy?: string;
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

// --- Projects & farms (Phase 1 — mirrors backend/schemas/projects.py & farms.py) ---

export type ProjectStatus = "planning" | "active" | "completed" | "archived";

export interface ProjectOut {
  project_id: string;
  name: string;
  description: string;
  geography: string;
  monitoring_start_date: string | null;
  monitoring_end_date: string | null;
  status: ProjectStatus;
  created_by: string | null;
  created_at: string | null;
}

export interface FarmOut {
  farm_id: string;
  name: string;
  contact_name: string;
  contact_phone: string;
  contact_email: string;
  consent_given: boolean;
  consent_reference: string;
  notes: string;
  created_by: string | null;
  created_at: string | null;
}

export interface FieldMembershipOut {
  membership_id: string;
  field_id: string;
  effective_start_date: string;
  effective_end_date: string | null;
  assigned_by: string | null;
  assigned_at: string | null;
  removed_at: string | null;
  removed_reason: string | null;
}

// --- Evidence-linked calculations (Phase 2 — mirrors src/calculations.py & src/readiness.py) ---

export type AccountingPathway = "vm0051_rice_awd" | "vm0042_alm";
export type CalculationStatus = "draft" | "ready_for_review" | "superseded";
export type ReadinessStatus = "satisfied" | "missing" | "needs_review" | "not_applicable" | "unsupported";

export type ImplementationSupport = "implemented" | "partial" | "unsupported";
export type ReviewerAuthority = "automated_only" | "reviewable" | "expert_required";

export interface ReadinessCheck {
  requirement_id: string;
  status: ReadinessStatus;
  explanation: string;
  evidence_references: { type: string; id: string }[];
  source_reference: string | null;
  required_evidence: string | null;
  implementation_support: ImplementationSupport | null;
  reviewer_authority: ReviewerAuthority | null;
  determination: "automated" | "expert";
  decided_by: string | null;
  reason: string | null;
}

export interface CalculationOut {
  calculation_id: string;
  chain_id: string;
  version: number;
  supersedes_calculation_id: string | null;
  project_id: string | null;
  field_id: string;
  field_type: FieldType;
  accounting_pathway: AccountingPathway;
  monitoring_period_start: string;
  monitoring_period_end: string;
  season_ids: string[];
  status: CalculationStatus;
  snapshot: Record<string, unknown>;
  inputs: Record<string, unknown>;
  result: CarbonResult;
  readiness: ReadinessCheck[];
  methodology_version: string;
  engine_version: string;
  final_issuance: number | null;
  created_by: string;
  created_at: string;
  legacy?: boolean;
  has_snapshot?: boolean;
}

export interface LegacyCalculationRow {
  legacy: true;
  has_snapshot: false;
  calculation_id: null;
  credit_history_id: number;
  created_at: string;
  final_issuance: number;
  inputs: Record<string, unknown>;
  result: CarbonResult;
}

export type CalculationHistoryRow = (CalculationOut & { legacy: false; has_snapshot: true }) | LegacyCalculationRow;

// --- Internal review (Phase 3 — mirrors src/reviews.py) ---

export type SubmissionStatus = "submitted" | "in_review" | "changes_requested" | "internally_approved" | "rejected" | "withdrawn";
export type FindingSeverity = "blocking" | "major" | "minor" | "info";

export interface ReviewSubmissionOut {
  org_id: string;
  submission_id: string;
  project_id: string;
  field_id: string;
  calculation_id: string;
  chain_id: string;
  previous_submission_id: string | null;
  status: SubmissionStatus;
  version: number;
  assigned_reviewer_id: string | null;
  submitted_by: string;
  submitted_at: string;
  decided_at: string | null;
  decision_reason: string | null;
  overdue?: boolean;
}

export interface FindingOut {
  finding_id: string;
  submission_id: string;
  requirement_id: string | null;
  input_ref: string | null;
  evidence_ref: string | null;
  severity: FindingSeverity;
  description: string;
  requested_action: string;
  author: string;
  status: "open" | "closed";
  closed_by: string | null;
  closed_at: string | null;
  close_reason: string | null;
  carried_from_finding_id: string | null;
  created_at: string;
}

export interface FindingCommentOut {
  id: string;
  finding_id: string;
  author: string;
  body: string;
  is_proposed_resolution: boolean;
  created_at: string;
}

export interface ReviewEventOut {
  id: string;
  submission_id: string;
  from_status: string;
  to_status: string;
  actor: string;
  reason: string | null;
  created_at: string;
}

export interface ReviewerAssignmentOut {
  id: string;
  submission_id: string;
  reviewer_id: string | null;
  assigned_by: string;
  reason: string;
  created_at: string;
}

export interface SubmissionDetailOut {
  submission: ReviewSubmissionOut;
  calculation: CalculationOut;
  findings: FindingOut[];
  events: ReviewEventOut[];
  assignment_history: ReviewerAssignmentOut[];
}

export interface SubmissionDiffOut {
  previous_calculation_id: string;
  current_calculation_id: string;
  inputs_changed: Record<string, { previous: unknown; current: unknown }>;
  result_changed: Record<string, { previous: unknown; current: unknown }>;
  readiness_changed: Record<string, { previous: string | null; current: string | null }>;
  season_ids_changed: boolean;
}

export interface NotificationOut {
  id: string;
  user_id: string;
  kind: string;
  submission_id: string | null;
  finding_id: string | null;
  message: string;
  read_at: string | null;
  created_at: string;
}
