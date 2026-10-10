"use client";

import { formatDate } from "@/lib/format";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { useProjectContext } from "@/components/projects/ProjectContext";
import { useFields } from "@/hooks/use-fields";
import { MethodologyCoverage } from "@/components/ai/MethodologyCoverage";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  useMethodologyBundles, useProjectApplicability, useProjectEligibleArea, useSetProjectApplicability,
} from "@/hooks/use-methodology";
import type { AccountingPathway } from "@/types/api";

const PATHWAYS: { value: AccountingPathway; label: string }[] = [
  { value: "vm0051_rice_awd", label: "VM0051 — Rice AWD" },
  { value: "vm0042_alm", label: "VM0042 — Improved Agricultural Land Management" },
];

function PathwaySection({ projectId, pathway, label, canManage }: { projectId: string; pathway: AccountingPathway; label: string; canManage: boolean }) {
  const bundles = useMethodologyBundles(pathway);
  const applicability = useProjectApplicability(projectId, pathway);
  const setApplicability = useSetProjectApplicability(projectId);
  const [bundleId, setBundleId] = useState("");
  const [reason, setReason] = useState("");
  const toast = useToast();

  const resolved = applicability.data?.resolved_bundle;
  const explicit = applicability.data?.explicit_decision as { bundle_id: string; reason: string; decided_at: string } | null;

  return (
    <Card>
      <h3 className="ui-subsection-title mb-2">{label}</h3>
      {applicability.isLoading ? <Skeleton className="h-16" /> : applicability.error ? (
        <Alert tone="danger" title="Could not load the methodology version">{applicability.error.message}</Alert>
      ) : (
        <>
          <p className="text-sm">
            Version used by new calculations: <strong>{resolved?.bundle_version ?? "none"}</strong>
            {resolved?.effective_from && ` (in force from ${formatDate(resolved.effective_from)})`}
          </p>
          {explicit ? (
            <p className="mt-1 text-xs text-text-secondary">
              Fixed for this project: {explicit.reason} (decided {formatDate(explicit.decided_at)})
            </p>
          ) : (
            <p className="ui-meta mt-1">Not fixed — the project follows the latest version.</p>
          )}
        </>
      )}
      <MethodologyCoverage projectId={projectId} pathway={pathway} />
      {canManage && <details className="mt-3">
        <summary className="cursor-pointer text-sm underline">Fix this project to a specific version</summary>
        <p className="ui-meta mt-2">Use this when the project must stay on an earlier version (for example, transition eligibility).</p>
        <form className="mt-2 flex flex-wrap gap-2" onSubmit={(e) => {
          e.preventDefault();
          setApplicability.mutateAsync({ accounting_pathway: pathway, bundle_id: bundleId, reason })
            .then(() => { setBundleId(""); setReason(""); toast.success("Methodology version fixed for this project"); })
            .catch((err) => toast.error(err, "Couldn't fix the methodology version"));
        }}>
          <Select aria-label="Methodology version" value={bundleId} onChange={(e) => setBundleId(e.target.value)} required className="max-w-sm">
            <option value="">Choose a version…</option>
            {(bundles.data ?? []).map((b) => (
              <option key={b.bundle_id} value={b.bundle_id}>
                {b.bundle_version}{b.is_current ? " (current)" : ""}
              </option>
            ))}
          </Select>
          <TextInput aria-label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (e.g. transition eligibility)" required className="flex-1" />
          <Button type="submit" variant="secondary" size="sm" loading={setApplicability.isPending}>Save</Button>
        </form>
      </details>}
    </Card>
  );
}

export default function ProjectMethodologyPage() {
  const project = useProjectContext();
  const eligibleArea = useProjectEligibleArea(project.project_id);
  const fields = useFields();
  const fieldName = (id: string) => fields.data?.find((f) => f.field_id === id)?.name ?? id;
  // Only the methodologies the project's fields actually use.
  const pathways = PATHWAYS.filter((p) => project.pathways.includes(p.value));

  return (
    <div className="ui-container space-y-6">
      <div>
        <h2 className="ui-section-title">Methodology</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Each new calculation records the methodology version below, so later Verra updates never change saved results.
        </p>
      </div>

      {pathways.length ? pathways.map((p) => (
        <PathwaySection key={p.value} projectId={project.project_id} pathway={p.value} label={p.label} canManage={project.can_manage} />
      )) : <p className="ui-secondary">Add fields to the project to see the methodology they follow.</p>}

      <Card>
        <h3 className="ui-subsection-title mb-2">Eligible area</h3>
        {eligibleArea.isLoading ? <Skeleton className="h-16" /> : eligibleArea.error ? (
          <Alert tone="danger" title="Could not load the eligible area">{eligibleArea.error.message}</Alert>
        ) : eligibleArea.data && (
          <>
            <p className="text-sm">
              {eligibleArea.data.field_count} field(s) in the project. Eligible:{" "}
              <Badge tone="success">{eligibleArea.data.totals_ha.eligible?.toFixed(2) ?? 0} ha</Badge>{" "}
              Excluded: <Badge tone="danger">{eligibleArea.data.totals_ha.excluded?.toFixed(2) ?? 0} ha</Badge>{" "}
              Needs review: <Badge tone="warning">{eligibleArea.data.totals_ha.needs_review?.toFixed(2) ?? 0} ha</Badge>
            </p>
            <p className="ui-meta mt-2">{eligibleArea.data.note}</p>
            {!!eligibleArea.data.fields_without_quantification_units.length && (
              <p className="ui-meta mt-1">
                Fields without an eligibility unit (counted in full as needs review):{" "}
                {eligibleArea.data.fields_without_quantification_units.map(fieldName).join(", ")}
              </p>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
