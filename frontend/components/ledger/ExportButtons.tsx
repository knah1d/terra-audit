"use client";

import { FileJson, FileSpreadsheet, FileText } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { useExportField } from "@/hooks/use-export";

/**
 * "Export Evidence Package" — PDF/JSON/CSV downloads, the frontend
 * counterpart of app.py's three st.download_button calls. Enabled once a
 * credit-history entry exists; the backend 409s otherwise (no committed
 * calculation to export yet), so committed gates the buttons here instead
 * of letting the request round-trip into a caught error every time.
 */
export function ExportButtons({
  fieldId,
  fieldType,
  committed,
}: {
  fieldId: string;
  fieldType: string;
  committed: boolean;
}) {
  const { download, pending, error } = useExportField(fieldId, fieldType);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-text-primary">Export Evidence Package</span>
        <Button
          variant="secondary"
          size="sm"
          icon={FileText}
          loading={pending === "pdf"}
          disabled={!committed || pending !== null}
          onClick={() => download("pdf")}
        >
          PDF
        </Button>
        <Button
          variant="secondary"
          size="sm"
          icon={FileJson}
          loading={pending === "json"}
          disabled={!committed || pending !== null}
          onClick={() => download("json")}
        >
          Audit JSON
        </Button>
        <Button
          variant="secondary"
          size="sm"
          icon={FileSpreadsheet}
          loading={pending === "csv"}
          disabled={!committed || pending !== null}
          onClick={() => download("csv")}
        >
          Data CSV
        </Button>
      </div>
      {!committed && (
        <p className="text-xs text-text-tertiary">Calculate &amp; save carbon credits first to enable export.</p>
      )}
      {error && <Alert tone="danger">{error}</Alert>}
    </div>
  );
}
