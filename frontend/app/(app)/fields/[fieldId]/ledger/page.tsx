"use client";

import Link from "next/link";
import { useFieldContext } from "@/components/fields/FieldContext";
import { CreditHistoryTable } from "@/components/ledger/CreditHistoryTable";
import { LedgerAlmForm } from "@/components/ledger/LedgerAlmForm";
import { LedgerRiceForm } from "@/components/ledger/LedgerRiceForm";
import { Card } from "@/components/ui/Card";
import { useAlmCompleteness } from "@/hooks/use-alm";

function AlmLedger({ fieldId, defaultArea }: { fieldId: string; defaultArea: number }) {
  const { data: completeness, isLoading } = useAlmCompleteness(fieldId);

  if (isLoading) return <p className="text-sm text-gray-500">Checking practice data…</p>;

  if (!completeness?.ready) {
    return (
      <Card className="border-amber-300 bg-amber-50">
        <p className="mb-2 font-medium text-amber-800">Practice &amp; Soil Data incomplete</p>
        <ul className="mb-3 list-inside list-disc text-sm text-amber-800">
          {completeness?.problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
        <Link href={`/fields/${fieldId}/practice-data`} className="text-sm font-medium text-blue-600 hover:underline">
          Go to Practice &amp; Soil Data →
        </Link>
      </Card>
    );
  }

  return <LedgerAlmForm fieldId={fieldId} defaultArea={defaultArea} />;
}

export default function LedgerPage() {
  const field = useFieldContext();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold">💰 Carbon Asset Ledger</h2>
        <p className="text-sm text-gray-500">
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
        <h3 className="mb-2 text-sm font-semibold text-gray-700">🕘 Verification History</h3>
        <CreditHistoryTable fieldId={field.field_id} />
      </div>
    </div>
  );
}
