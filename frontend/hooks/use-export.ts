"use client";

import { useState } from "react";
import { apiFetchBlob, ApiError } from "@/lib/api";
import { downloadBlob } from "@/lib/download";

export type ExportFormat = "pdf" | "json" | "csv";

const CONTENT_TYPE: Record<ExportFormat, string> = {
  pdf: "application/pdf",
  json: "application/json",
  csv: "text/csv",
};

/**
 * Export/Evidence Package downloads — GET /fields/{fieldId}/verifications/
 * {verificationId}/evidence/{pdf|json|csv} (backend/routers/export.py).
 * Tied to a specific, immutable, committed credit_history row (its stable
 * id — never "whatever the field's latest mutable state happens to be").
 * The backend reconstructs the PDF/JSON from that row's stored inputs/
 * result rather than recomputing against current field state; CSV is
 * timeseries/practice data, existence/ownership-checked against the same
 * verification id but not itself drawn from the committed row.
 */
export function useExportField(fieldId: string, fieldType: string, verificationId: number | null) {
  const [pending, setPending] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function download(format: ExportFormat) {
    if (verificationId === null) return;
    setPending(format);
    setError(null);
    try {
      const blob = await apiFetchBlob(
        `/fields/${fieldId}/verifications/${verificationId}/evidence/${format}`,
      );
      const prefix = fieldType === "rice_awd" ? "terra_audit" : "terra_audit_alm";
      const fidSlug = fieldId.replace(/-/g, "").toLowerCase();
      const filename =
        format === "json" ? `audit_${fidSlug}_v${verificationId}.json`
        : format === "csv" ? `${fieldType === "rice_awd" ? "timeseries" : "alm_data"}_${fidSlug}_v${verificationId}.csv`
        : `${prefix}_${fidSlug}_v${verificationId}.pdf`;
      downloadBlob(new Blob([blob], { type: CONTENT_TYPE[format] }), filename);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `${format.toUpperCase()} export failed: ${err.detail}`
          : `${format.toUpperCase()} export failed`,
      );
    } finally {
      setPending(null);
    }
  }

  return { download, pending, error };
}
