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

/** SQL queue timestamps without an offset are legacy UTC values. */
export function formatQueueTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const normalized = value.trim().replace(" ", "T");
  const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized}Z`);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    year: "numeric", month: "numeric", day: "numeric",
    hour: "numeric", minute: "2-digit", second: "2-digit", timeZoneName: "short",
  });
}

export function formatNumber(value: number | null | undefined, unit: string = ""): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const decimals = DECIMALS[unit.toLowerCase()] ?? 2;
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
