"use client";

import { ArrowRight, Plus } from "lucide-react";
import Link from "next/link";
import { useProjectContext } from "@/components/projects/ProjectContext";
import { StepStatusBadge } from "@/components/fields/StepStatusBadge";
import { Alert } from "@/components/ui/Alert";
import { ButtonLink } from "@/components/ui/Button";
import { Card, StatCard } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { useProjectWorkflow } from "@/hooks/use-workflow";
import { stepLabel, stepSegment } from "@/lib/field-steps";

/** Project home: each field's progress (from saved records), what needs
 * attention, and the next action per field. */
export default function ProjectOverviewPage() {
  const project = useProjectContext();
  const workflow = useProjectWorkflow(project.project_id);
  const pid = encodeURIComponent(project.project_id);
  const rows = workflow.data ?? [];
  const attention = rows.filter((r) => Object.values(r.steps).some((s) => s.status === "needs_attention"));
  const ready = rows.filter((r) => r.steps.calculations?.status === "ready");
  const approved = rows.filter((r) => r.steps.review?.status === "completed");

  return (
    <div className="ui-container space-y-6">
      <div className="flex flex-wrap justify-end gap-2">
        <ButtonLink size="sm" variant="secondary" href={`/projects/${pid}/fields`}>Assign existing field</ButtonLink>
        <ButtonLink size="sm" href={`/fields/new?project=${pid}`} icon={Plus}>Register a field</ButtonLink>
      </div>
      {workflow.isLoading ? <Skeleton className="h-48" /> : workflow.error ? (
        <Alert tone="danger" title="Unable to load project progress">{workflow.error.message}</Alert>
      ) : !rows.length ? (
        <EmptyState title="No fields in this project yet" description="Register a new field for this project or assign a standalone field."
          action={<ButtonLink href={`/fields/new?project=${pid}`} icon={Plus}>Register a field</ButtonLink>} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Fields" value={String(rows.length)} />
            <StatCard label="Need attention" value={String(attention.length)} tone={attention.length ? "warning" : "neutral"} />
            <StatCard label="Ready calculations" value={String(ready.length)} tone={ready.length ? "success" : "neutral"} />
            <StatCard label="Internally approved" value={String(approved.length)} tone={approved.length ? "success" : "neutral"} />
          </div>
          <Card className="p-0">
            <ul className="divide-y divide-border-subtle">
              {rows.map((r) => {
                const base = `/fields/${encodeURIComponent(r.field_id)}`;
                return (
                  <li key={r.field_id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                    <div className="min-w-0">
                      <Link href={`${base}/overview`} className="font-medium hover:underline">{r.name}</Link>
                      <p className="ui-meta">{r.district}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {r.order.map((step) => (
                          <span key={step} className="inline-flex items-center gap-1 text-xs">
                            {stepLabel(step)}: <StepStatusBadge status={r.steps[step].status} />
                          </span>
                        ))}
                      </div>
                    </div>
                    {r.next_step && (
                      <ButtonLink size="sm" variant="secondary" href={`${base}/${stepSegment(r.next_step.step)}`} icon={ArrowRight} className="flex-row-reverse gap-2">
                        {r.next_step.step === "review" ? "Submit for review" : stepLabel(r.next_step.step)}
                      </ButtonLink>
                    )}
                  </li>
                );
              })}
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}
