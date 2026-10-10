"use client";
import Link from "next/link";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { RoleGate } from "@/components/ui/RoleGate";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  useCreateQuantificationUnit, useGuidedEnrollment, useQuantificationUnits,
} from "@/hooks/use-methodology";

const PATHWAY_LABEL: Record<string, string> = {
  vm0051_rice_awd: "VM0051 — Improved rice cultivation (AWD)", vm0042_alm: "VM0042 — Improved agricultural land management",
};
const yesNo = (v: boolean | null | undefined) => (v === true ? "yes" : v === false ? "no" : "unknown");

const SUPPORT_TONE: Record<string, "success" | "warning" | "neutral"> = {
  implemented: "success", partial: "warning", unsupported: "neutral",
};

export default function EnrollmentPage() {
  const field = useFieldContext();
  const enrollment = useGuidedEnrollment(field.field_id);
  const units = useQuantificationUnits(field.field_id);
  const createUnit = useCreateQuantificationUnit(field.field_id);
  const toast = useToast();
  const [eligibility, setEligibility] = useState("needs_review");

  const totalUnitArea = (units.data ?? []).reduce((sum, u) => sum + u.area_ha, 0);

  return (
    <div className="ui-container space-y-6">
      <div>
        <h2 className="ui-section-title">Guided enrollment</h2>
      </div>

      {enrollment.error && <Alert tone="danger" title="Could not load enrollment">{enrollment.error.message}</Alert>}
      {enrollment.isLoading ? <Skeleton className="h-64" /> : enrollment.data && (
        <>
          <Card>
            <h3 className="ui-subsection-title mb-2">Methodology</h3>
            <p className="text-sm">
              This field follows <strong>{PATHWAY_LABEL[enrollment.data.accounting_pathway ?? ""] ?? "no supported methodology"}</strong>.
            </p>
            {enrollment.data.methodology_bundle && (
              <p className="mt-1 text-sm text-text-secondary">
                Methodology version used: <strong>{enrollment.data.methodology_bundle.bundle_version}</strong>
                {enrollment.data.methodology_bundle.effective_from && ` (in force from ${enrollment.data.methodology_bundle.effective_from})`}
              </p>
            )}
          </Card>

          <Card>
            <h3 className="ui-subsection-title mb-2">Declared crops</h3>
            {!enrollment.data.declared_crops.length ? (
              <p className="ui-secondary">No crops declared yet — add a crop season first.</p>
            ) : (
              <div className="space-y-2">
                {enrollment.data.declared_crops.map((c, i) => (
                  <div key={i} className="text-sm">
                    <Badge tone={c.recognized ? "brand" : "neutral"}>{c.common_names[0]}</Badge>
                    {c.recognized ? (
                      <span className="ml-2 text-text-secondary">
                        Usually in scope for {field.field_type === "rice_awd" ? `VM0051: ${yesNo(c.vm0051_eligible)}` : `VM0042: ${yesNo(c.alm_eligible)}`}
                      </span>
                    ) : (
                      <span className="ml-2 text-text-secondary">Not in the recognized taxonomy — a reviewer must confirm applicability.</span>
                    )}
                    {c.notes && <p className="ui-meta ml-1 mt-0.5">{c.notes}</p>}
                  </div>
                ))}
              </div>
            )}
            {enrollment.data.declared_crops.some(c => !c.recognized || (field.field_type === "rice_awd" ? !c.vm0051_eligible : !c.alm_eligible)) && <p role="status" className="mt-3 text-warning-700">Some declared crops are outside this pathway&apos;s usual taxonomy scope. Confirm actual applicability with a reviewer before preparing an issuance claim. The field&apos;s registered methodology is unchanged.</p>}
          </Card>

          <Card>
            <h3 className="ui-subsection-title mb-2">Unsupported / partial scope for this bundle</h3>
            {!enrollment.data.unsupported_or_partial_scope.length ? (
              <p className="ui-secondary">Nothing flagged.</p>
            ) : (
              <div className="space-y-2">
                {enrollment.data.unsupported_or_partial_scope.map((s) => (
                  <div key={s.requirement_id} className="border-t border-border pt-2 text-sm first:border-t-0 first:pt-0">
                    <Badge tone={SUPPORT_TONE[s.implementation_support]}>{s.implementation_support}</Badge>{" "}
                    <span className="font-medium">{s.title}</span>
                    <p className="ui-meta">{s.required_evidence}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card>
            <h3 className="ui-subsection-title mb-2">Missing evidence</h3>
            {!enrollment.data.missing_evidence.length ? (
              <p className="ui-secondary">No evidence gaps flagged. <Link className="underline text-brand-700" href={`/fields/${field.field_id}/calculations`}>Run the full readiness checklist</Link>.</p>
            ) : (
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {enrollment.data.missing_evidence.map((m, i) => <li key={i}>{m}</li>)}
              </ul>
            )}
          </Card>
        </>
      )}

      <Card>
        <h3 className="ui-subsection-title mb-2">Quantification units</h3>
        <p className="ui-meta mb-3">
          Field area:{" "}
          {field.area_ha?.toFixed(2)} ha · allocated so far: {totalUnitArea.toFixed(2)} ha.
        </p>
        {units.isLoading ? <Skeleton className="h-16" /> : !units.data?.length ? (
          <p className="ui-secondary">No quantification units recorded.</p>
        ) : (
          <div className="mb-3 space-y-1 text-sm">
            {units.data.map((u) => (
              <p key={u.unit_id}>
                <Badge tone={u.eligibility_status === "eligible" ? "success" : u.eligibility_status === "excluded" ? "danger" : "warning"}>
                  {u.eligibility_status.replace(/_/g, " ")}
                </Badge>{" "}
                {u.name} — {u.area_ha.toFixed(2)} ha{u.exclusion_reason && ` (${u.exclusion_reason})`}
              </p>
            ))}
          </div>
        )}
        <RoleGate allow={["admin", "analyst"]}>
        <form className="grid gap-2 sm:grid-cols-2" onSubmit={(e) => {
          e.preventDefault();
          const data = new FormData(e.currentTarget);
          createUnit.mutateAsync({
            name: String(data.get("name")), area_ha: Number(data.get("area_ha")),
            eligibility_status: eligibility,
            exclusion_reason: eligibility === "excluded" ? String(data.get("exclusion_reason")) : undefined,
          }).then(() => { (e.target as HTMLFormElement).reset(); toast.success("Quantification unit added"); })
            .catch((err) => toast.error(err, "Couldn't add unit"));
        }}>
          <TextInput aria-label="Quantification unit name" name="name" placeholder="Unit name" required maxLength={200} />
          <TextInput aria-label="Quantification unit area in hectares" name="area_ha" type="number" step="any" placeholder="Area (ha)" required min={0.01} />
          <Select aria-label="Quantification unit eligibility" value={eligibility} onChange={(e) => setEligibility(e.target.value)}>
            <option value="needs_review">Needs review</option>
            <option value="eligible">Eligible</option>
            <option value="excluded">Excluded</option>
          </Select>
          {eligibility === "excluded" && <TextInput aria-label="Reason for excluding this unit" name="exclusion_reason" placeholder="Exclusion reason (required)" required maxLength={2000} />}
          <div className="sm:col-span-2"><Button type="submit" loading={createUnit.isPending}>Add quantification unit</Button></div>
        </form>
        </RoleGate>
      </Card>
    </div>
  );
}
