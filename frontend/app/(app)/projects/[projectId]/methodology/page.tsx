"use client";

import { useState } from "react";
import { useProjectContext } from "@/components/projects/ProjectContext";
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

function PathwaySection({ projectId, pathway, label }: { projectId: string; pathway: AccountingPathway; label: string }) {
  const bundles = useMethodologyBundles(pathway);
  const applicability = useProjectApplicability(projectId, pathway);
  const setApplicability = useSetProjectApplicability(projectId);
  const [bundleId, setBundleId] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  const resolved = applicability.data?.resolved_bundle;
  const explicit = applicability.data?.explicit_decision as { bundle_id: string; reason: string; decided_at: string } | null;

  return (
    <Card>
      <h3 className="mb-2 font-medium">{label}</h3>
      {applicability.isLoading ? <Skeleton className="h-16" /> : (
        <>
          <p className="text-sm">
            Currently resolved bundle: <strong>{resolved?.bundle_version ?? "none"}</strong>
            {resolved?.effective_from && ` (effective ${resolved.effective_from})`}
          </p>
          {explicit ? (
            <p className="mt-1 text-xs text-text-secondary">
              Explicitly pinned: {explicit.reason} (decided {new Date(explicit.decided_at).toLocaleDateString()})
            </p>
          ) : (
            <p className="mt-1 text-xs text-text-tertiary">No explicit decision recorded — using whichever bundle is currently marked current.</p>
          )}
        </>
      )}
      <details className="mt-3">
        <summary className="cursor-pointer text-sm underline">Pin this project to a specific bundle (project lead/admin only)</summary>
        <form className="mt-2 flex flex-wrap gap-2" onSubmit={(e) => {
          e.preventDefault();
          setError("");
          setApplicability.mutateAsync({ accounting_pathway: pathway, bundle_id: bundleId, reason })
            .then(() => { setBundleId(""); setReason(""); })
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to set applicability"));
        }}>
          <Select value={bundleId} onChange={(e) => setBundleId(e.target.value)} required className="max-w-sm">
            <option value="">Choose a bundle…</option>
            {(bundles.data ?? []).map((b) => (
              <option key={b.bundle_id} value={b.bundle_id}>
                {b.bundle_version}{b.is_current ? " (current)" : ""}
              </option>
            ))}
          </Select>
          <TextInput value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (e.g. transition eligibility)" required className="flex-1" />
          <Button type="submit" variant="secondary" size="sm" loading={setApplicability.isPending}>Pin bundle</Button>
        </form>
        {error && <p role="alert" className="mt-2 text-sm text-danger-700">{error}</p>}
      </details>
    </Card>
  );
}

export default function ProjectMethodologyPage() {
  const project = useProjectContext();
  const eligibleArea = useProjectEligibleArea(project.project_id);

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Methodology</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Every new calculation freezes the resolved bundle below into its snapshot. Pinning a project to a specific
          bundle (e.g. a superseded version a project is transition-eligible for) overrides the default
          &quot;whichever bundle is currently marked current&quot; resolution.
        </p>
      </div>

      {PATHWAYS.map((p) => (
        <PathwaySection key={p.value} projectId={project.project_id} pathway={p.value} label={p.label} />
      ))}

      <Card>
        <h3 className="mb-2 font-medium">Grouped-project eligible area</h3>
        {eligibleArea.isLoading ? <Skeleton className="h-16" /> : eligibleArea.data && (
          <>
            <p className="text-sm">
              {eligibleArea.data.field_count} field(s) assigned. Eligible:{" "}
              <Badge tone="success">{eligibleArea.data.totals_ha.eligible?.toFixed(2) ?? 0} ha</Badge>{" "}
              Excluded: <Badge tone="danger">{eligibleArea.data.totals_ha.excluded?.toFixed(2) ?? 0} ha</Badge>{" "}
              Needs review: <Badge tone="warning">{eligibleArea.data.totals_ha.needs_review?.toFixed(2) ?? 0} ha</Badge>
            </p>
            <p className="mt-2 text-xs text-text-tertiary">{eligibleArea.data.note}</p>
            {!!eligibleArea.data.fields_without_quantification_units.length && (
              <p className="mt-1 text-xs text-text-tertiary">
                Fields with no quantification unit recorded (counted in full under needs_review):{" "}
                {eligibleArea.data.fields_without_quantification_units.join(", ")}
              </p>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
