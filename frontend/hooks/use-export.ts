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
 * Export/Evidence Package downloads — GET /fields/{fieldId}/export/{pdf|json|csv}
 * (backend/routers/export.py) already reconstructs everything server-side
 * from the persisted signal-run job / credit-history / practice-schedule
 * rows, so this hook is just fetch-as-blob + browser download; no
 * session-state export_* keys to assemble client-side the way Streamlit did.
 *
 * There is no credit_history_id picker: the backend only supports "latest"
 * today (a specific id 501s), so this hook never sends one.
 */
export function useExportField(fieldId: string, fieldType: string) {
  const [pending, setPending] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function download(format: ExportFormat) {
    setPending(format);
    setError(null);
    try {
      const blob = await apiFetchBlob(`/fields/${fieldId}/export/${format}`);
      const prefix = fieldType === "rice_awd" ? "terra_audit" : "terra_audit_alm";
      const fidSlug = fieldId.replace(/-/g, "").toLowerCase();
      const filename =
        format === "json" ? `audit_${fidSlug}.json`
        : format === "csv" ? `${fieldType === "rice_awd" ? "timeseries" : "alm_data"}_${fidSlug}.csv`
        : `${prefix}_${fidSlug}.pdf`;
      downloadBlob(new Blob([blob], { type: CONTENT_TYPE[format] }), filename);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Export failed");
    } finally {
      setPending(null);
    }
  }

  return { download, pending, error };
}
