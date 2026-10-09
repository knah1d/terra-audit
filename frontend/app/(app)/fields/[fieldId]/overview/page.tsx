"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useFieldContext } from "@/components/fields/FieldContext";
import { StepStatusBadge } from "@/components/fields/StepStatusBadge";
import { Alert } from "@/components/ui/Alert";
import { ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { useFieldWorkflow } from "@/hooks/use-workflow";
import { stepLabel, stepSegment } from "@/lib/field-steps";

/** Field home: every step's status (from saved records) and one Next step. */
export default function FieldOverviewPage() {
  const field = useFieldContext();
  const workflow = useFieldWorkflow(field.field_id);
  const base = `/fields/${encodeURIComponent(field.field_id)}`;

  if (workflow.isLoading) return <div className="ui-container"><Skeleton className="h-48" /></div>;
  if (workflow.error || !workflow.data) {
    return <div className="ui-container"><Alert tone="danger" title="Unable to load progress">{workflow.error?.message}</Alert></div>;
  }
  const { steps, order, next_step } = workflow.data;

  return (
    <div className="ui-container space-y-6">
      <Card className="flex flex-wrap items-center justify-between gap-4">
        {next_step ? (
          <>
            <div>
              <p className="ui-meta">Next step</p>
              <p className="ui-subsection-title">{next_step.step === "review" ? "Submit for review" : stepLabel(next_step.step)}</p>
              <p className="ui-secondary">{next_step.detail}</p>
            </div>
            <ButtonLink href={`${base}/${stepSegment(next_step.step)}`} icon={ArrowRight} className="flex-row-reverse gap-2">Continue</ButtonLink>
          </>
        ) : (
          <p className="ui-subsection-title">All steps are complete.</p>
        )}
      </Card>

      <Card className="p-0">
        <ol className="divide-y divide-border-subtle">
          {order.map((step, i) => {
            const s = steps[step];
            return (
              <li key={step}>
                <Link href={`${base}/${stepSegment(step)}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 hover:bg-surface-muted/40">
                  <span className="flex min-w-0 items-center gap-3">
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border text-xs tabular-nums">{i + 1}</span>
                    <span className="min-w-0">
                      <span className="block font-medium">{stepLabel(step)}</span>
                      <span className="ui-meta">{s.detail}</span>
                    </span>
                  </span>
                  <StepStatusBadge status={s.status} />
                </Link>
              </li>
            );
          })}
        </ol>
      </Card>
    </div>
  );
}
