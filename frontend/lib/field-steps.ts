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
  { segment: "crop-seasons", label: "Crop Seasons", numbered: true },
  { segment: "enrollment", label: "Enrollment", numbered: true },
  { segment: "signal-analytics", label: "Signal Analytics", numbered: true },
  { segment: "awd-validation", label: "AWD Check (ML)", numbered: true },
  { segment: "calculations", label: "Calculations", numbered: true },
  { segment: "evidence-files", label: "Evidence Files", numbered: false },
];

const ALM_STEPS: FieldStep[] = [
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

/** Where a field opens: its first workflow step. */
export function firstStepPath(fieldId: string, fieldType: string): string {
  return `/fields/${encodeURIComponent(fieldId)}/${fieldSteps(fieldType)[0].segment}`;
}
