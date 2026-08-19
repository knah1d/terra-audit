/**
 * Centralizes numeric display precision so every derivation step and
 * result card is consistent — per-unit decimal places matching the
 * backend's own formatting conventions (see src/report_generator.py's
 * .4f usage for tCO2e figures).
 */
const DECIMALS: Record<string, number> = {
  tco2e: 4,
  "kg ch4/ha/day": 2,
  "kg/ha": 2,
  "t/ha": 2,
  "%": 1,
  ha: 4,
  days: 0,
  "": 2,
};

export function formatNumber(value: number | null | undefined, unit: string = ""): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const decimals = DECIMALS[unit.toLowerCase()] ?? 2;
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
