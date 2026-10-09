/**
 * Field workflow steps in prerequisite order — each step's data feeds the
 * next (crop seasons → enrollment summary → field data → checks →
 * calculations). Shared by the tab bar and every redirect into a field, so
 * they can never disagree about where a field "starts".
 *
 * Plain module (no "use client") so server components (field index redirect)
 * and client components (tabs, forms) can both use it.
 */
export type FieldStep = { segment: string; label: string; numbered: boolean };

const RICE_STEPS: FieldStep[] = [
  { segment: "overview", label: "Overview", numbered: false },
  { segment: "crop-seasons", label: "Crop Seasons", numbered: true },
  { segment: "enrollment", label: "Enrollment", numbered: true },
  { segment: "signal-analytics", label: "Signal Analytics", numbered: true },
  { segment: "awd-validation", label: "AWD Check (ML)", numbered: true },
  { segment: "calculations", label: "Calculations", numbered: true },
  { segment: "evidence-files", label: "Evidence Files", numbered: false },
];

const ALM_STEPS: FieldStep[] = [
  { segment: "overview", label: "Overview", numbered: false },
  { segment: "crop-seasons", label: "Crop Seasons", numbered: true },
  { segment: "enrollment", label: "Enrollment", numbered: true },
  { segment: "practice-data", label: "Practice & Soil Data", numbered: true },
  { segment: "soil-evidence", label: "Soil Sampling", numbered: true },
  { segment: "production-records", label: "Production Records", numbered: true },
  { segment: "calculations", label: "Calculations", numbered: true },
  { segment: "evidence-files", label: "Evidence Files", numbered: false },
];

export function fieldSteps(fieldType: string): FieldStep[] {
  return fieldType === "rice_awd" ? RICE_STEPS : ALM_STEPS;
}

/** Label for a workflow step id, including "review" (no tab of its own —
 * submission happens from Calculations). */
export function stepLabel(segment: string): string {
  if (segment === "review") return "Review";
  return [...RICE_STEPS, ...ALM_STEPS].find((s) => s.segment === segment)?.label ?? segment;
}

/** Tab that holds a workflow step ("review" is done from Calculations). */
export function stepSegment(step: string): string {
  return step === "review" ? "calculations" : step;
}

/** Where a field opens: its Overview (statuses + next step). */
export function firstStepPath(fieldId: string, fieldType: string): string {
  return `/fields/${encodeURIComponent(fieldId)}/${fieldSteps(fieldType)[0].segment}`;
}
