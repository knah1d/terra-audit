"use client";

import { FileJson, FileSpreadsheet, FileText } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { useExportField } from "@/hooks/use-export";

/**
 * "Export Evidence Package" — PDF/JSON/CSV downloads, the frontend
 * counterpart of app.py's three st.download_button calls. Tied to one
 * specific committed verification (verificationId — the latest
 * credit_history row's stable id); null means nothing has been committed
 * yet, which also disables the buttons.
 */
export function ExportButtons({
  fieldId,
  fieldType,
  verificationId,
}: {
  fieldId: string;
  fieldType: string;
  verificationId: number | null;
}) {
  const committed = verificationId !== null;
  const { download, pending, error } = useExportField(fieldId, fieldType, verificationId);

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
