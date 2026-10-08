"use client";

import { ArrowRight, FlaskConical, History, Wallet } from "lucide-react";
import Link from "next/link";
import { useFieldContext } from "@/components/fields/FieldContext";
import { CreditHistoryTable } from "@/components/ledger/CreditHistoryTable";
import { LedgerAlmForm } from "@/components/ledger/LedgerAlmForm";
import { LedgerRiceForm } from "@/components/ledger/LedgerRiceForm";
import { ButtonLink } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconTile } from "@/components/ui/IconTile";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAlmCompleteness } from "@/hooks/use-alm";

function AlmLedger({ fieldId, defaultArea }: { fieldId: string; defaultArea: number }) {
  const { data: completeness, isLoading } = useAlmCompleteness(fieldId);

  if (isLoading) return <Skeleton className="h-32" />;

  if (!completeness?.ready) {
    const problems = completeness?.problems ?? [];
    return (
      <EmptyState
        icon={FlaskConical}
        title="Add practice & soil data to calculate"
        description={problems.length ? `${problems.length} required ${problems.length === 1 ? "item is" : "items are"} still missing for this field.` : undefined}
        action={
          <div className="flex flex-col items-center gap-3">
            <ButtonLink href={`/fields/${fieldId}/practice-data`} icon={ArrowRight}>
              Go to Practice &amp; Soil Data
            </ButtonLink>
            {!!problems.length && (
              <details className="text-left text-sm text-text-secondary">
                <summary className="cursor-pointer text-center">Show what&apos;s missing</summary>
                <ul className="mt-2 list-inside list-disc">
                  {problems.map((p) => <li key={p}>{p}</li>)}
                </ul>
              </details>
            )}
          </div>
        }
      />
    );
  }

  return <LedgerAlmForm fieldId={fieldId} defaultArea={defaultArea} />;
}

export default function LedgerPage() {
  const field = useFieldContext();

  return (
    <div className="ui-container flex flex-col gap-6">
      <div>
        <h2 className="ui-section-title flex items-center gap-3">
          <IconTile icon={Wallet} size="sm" />
          Carbon Asset Ledger
        </h2>
        <p className="ui-secondary">
          {field.field_type === "rice_awd"
            ? "VM0051 QA3 (Default Emission Factors) pathway."
            : "VM0042 — Improved Agricultural Land Management."}
        </p>
        <p className="ui-meta mt-1">
          Legacy estimates, not issued credits. Use{" "}
          <Link className="underline" href={`/fields/${field.field_id}/calculations`}>Calculations</Link>{" "}
          for evidence-linked runs and review.
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
          Legacy calculation history
        </h3>
        <CreditHistoryTable fieldId={field.field_id} />
      </div>
    </div>
  );
}
