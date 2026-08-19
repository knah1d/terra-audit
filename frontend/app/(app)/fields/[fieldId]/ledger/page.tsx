"use client";

import { ArrowRight, History, Wallet } from "lucide-react";
import Link from "next/link";
import { useFieldContext } from "@/components/fields/FieldContext";
import { CreditHistoryTable } from "@/components/ledger/CreditHistoryTable";
import { LedgerAlmForm } from "@/components/ledger/LedgerAlmForm";
import { LedgerRiceForm } from "@/components/ledger/LedgerRiceForm";
import { Alert } from "@/components/ui/Alert";
import { IconTile } from "@/components/ui/IconTile";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAlmCompleteness } from "@/hooks/use-alm";

function AlmLedger({ fieldId, defaultArea }: { fieldId: string; defaultArea: number }) {
  const { data: completeness, isLoading } = useAlmCompleteness(fieldId);

  if (isLoading) return <Skeleton className="h-32" />;

  if (!completeness?.ready) {
    return (
      <Alert tone="warning" title="Practice & Soil Data incomplete">
        <ul className="mb-2 list-inside list-disc">
          {completeness?.problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
        <Link
          href={`/fields/${fieldId}/practice-data`}
          className="inline-flex items-center gap-1 font-medium text-warning-700 hover:underline"
        >
          Go to Practice &amp; Soil Data
          <ArrowRight className="size-3.5" />
        </Link>
      </Alert>
    );
  }

  return <LedgerAlmForm fieldId={fieldId} defaultArea={defaultArea} />;
}

export default function LedgerPage() {
  const field = useFieldContext();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="flex items-center gap-2.5 text-lg font-semibold text-text-primary">
          <IconTile icon={Wallet} size="sm" />
          Carbon Asset Ledger
        </h2>
        <p className="text-sm text-text-secondary">
          {field.field_type === "rice_awd"
            ? "VM0051 QA3 (Default Emission Factors) pathway."
            : "VM0042 — Improved Agricultural Land Management."}
        </p>
      </div>

      {field.field_type === "rice_awd" ? (
        <LedgerRiceForm fieldId={field.field_id} defaultArea={field.area_ha ?? 1} />
      ) : (
        <AlmLedger fieldId={field.field_id} defaultArea={field.area_ha ?? 1} />
      )}

      <div>
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-text-secondary">
          <History className="size-4" />
          Verification History
        </h3>
        <CreditHistoryTable fieldId={field.field_id} />
      </div>
    </div>
  );
}
