/**
 * Centralizes numeric display precision so every derivation step and
 * result card is consistent — per-unit decimal places matching the
 * backend's own formatting conventions (see src/reporting/reports.py's
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
  return `${formatDate(date)} ${date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false, timeZoneName: "short" })}`;
}

export function formatNumber(value: number | null | undefined, unit: string = ""): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const decimals = DECIMALS[unit.toLowerCase()] ?? 2;
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Date-only records are calendar dates; never shift them between timezones. */
export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return "—";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value.split("-").reverse().join("-");
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return [date.getDate(), date.getMonth() + 1, date.getFullYear()].map((n, i) => String(n).padStart(i === 2 ? 4 : 2, "0")).join("-");
}
