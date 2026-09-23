"use client";

import { useState } from "react";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  useCreateQuantificationUnit, useGuidedEnrollment, useQuantificationUnits,
} from "@/hooks/use-methodology";

const SUPPORT_TONE: Record<string, "success" | "warning" | "neutral"> = {
  implemented: "success", partial: "warning", unsupported: "neutral",
};

export default function EnrollmentPage() {
  const field = useFieldContext();
  const enrollment = useGuidedEnrollment(field.field_id);
  const units = useQuantificationUnits(field.field_id);
  const createUnit = useCreateQuantificationUnit(field.field_id);
  const [error, setError] = useState("");
  const [eligibility, setEligibility] = useState("needs_review");

  const totalUnitArea = (units.data ?? []).reduce((sum, u) => sum + u.area_ha, 0);

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Guided enrollment</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Shows which pathway this field&apos;s type maps to, what this codebase does and does not implement for it,
          and the most basic missing-evidence flags — not a substitute for the full readiness checklist run at
          calculation time.
        </p>
      </div>
      {error && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{error}</p>}

      {enrollment.isLoading ? <Skeleton className="h-64" /> : enrollment.data && (
        <>
          <Card>
            <h3 className="mb-2 font-medium">Pathway</h3>
            <p className="text-sm">
              Field type <span className="font-mono">{enrollment.data.field_type}</span> maps to pathway{" "}
              <span className="font-mono">{enrollment.data.accounting_pathway ?? "none"}</span>.
            </p>
            {enrollment.data.methodology_bundle && (
              <p className="mt-1 text-sm text-text-secondary">
                Current methodology bundle: <strong>{enrollment.data.methodology_bundle.bundle_version}</strong>
                {enrollment.data.methodology_bundle.effective_from && ` (effective ${enrollment.data.methodology_bundle.effective_from})`}
              </p>
            )}
          </Card>

          <Card>
            <h3 className="mb-2 font-medium">Declared crops</h3>
            {!enrollment.data.declared_crops.length ? (
              <p className="text-sm text-text-secondary">No crops declared yet — add a crop season first.</p>
            ) : (
              <div className="space-y-2">
                {enrollment.data.declared_crops.map((c, i) => (
                  <div key={i} className="text-sm">
                    <Badge tone={c.recognized ? "brand" : "neutral"}>{c.common_names[0]}</Badge>
                    {c.recognized ? (
                      <span className="ml-2 text-text-secondary">
                        ALM-eligible signal: {String(c.alm_eligible)} · VM0051-eligible signal: {String(c.vm0051_eligible)}
                      </span>
                    ) : (
                      <span className="ml-2 text-text-secondary">Not in the recognized taxonomy — a reviewer must confirm applicability.</span>
                    )}
                    {c.notes && <p className="ml-1 mt-0.5 text-xs text-text-tertiary">{c.notes}</p>}
                  </div>
                ))}
              </div>
            )}
            <p className="mt-2 text-xs text-text-tertiary">
              These are indicative signals only — never a full applicability determination by themselves.
            </p>
          </Card>

          <Card>
            <h3 className="mb-2 font-medium">Unsupported / partial scope for this bundle</h3>
            {!enrollment.data.unsupported_or_partial_scope.length ? (
              <p className="text-sm text-text-secondary">Nothing flagged.</p>
            ) : (
              <div className="space-y-2">
                {enrollment.data.unsupported_or_partial_scope.map((s) => (
                  <div key={s.requirement_id} className="border-t border-border pt-2 text-sm first:border-t-0 first:pt-0">
                    <Badge tone={SUPPORT_TONE[s.implementation_support]}>{s.implementation_support}</Badge>{" "}
                    <span className="font-medium">{s.title}</span>
                    <p className="text-xs text-text-tertiary">{s.required_evidence}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card>
            <h3 className="mb-2 font-medium">Missing evidence</h3>
            {!enrollment.data.missing_evidence.length ? (
              <p className="text-sm text-success-700">No basic evidence gaps flagged.</p>
            ) : (
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {enrollment.data.missing_evidence.map((m, i) => <li key={i}>{m}</li>)}
              </ul>
            )}
          </Card>
        </>
      )}

      <Card>
        <h3 className="mb-2 font-medium">Quantification units</h3>
        <p className="mb-3 text-xs text-text-tertiary">
          Named subdivisions of this field&apos;s registered area for eligibility purposes — this never resizes the
          field itself, only records how much of it is currently considered eligible and why. Field area:{" "}
          {field.area_ha?.toFixed(2)} ha · allocated so far: {totalUnitArea.toFixed(2)} ha.
        </p>
        {units.isLoading ? <Skeleton className="h-16" /> : !units.data?.length ? (
          <p className="text-sm text-text-secondary">No quantification units recorded — the whole field is treated as needs_review by default.</p>
        ) : (
          <div className="mb-3 space-y-1 text-sm">
            {units.data.map((u) => (
              <p key={u.unit_id}>
                <Badge tone={u.eligibility_status === "eligible" ? "success" : u.eligibility_status === "excluded" ? "danger" : "warning"}>
                  {u.eligibility_status}
                </Badge>{" "}
                {u.name} — {u.area_ha.toFixed(2)} ha{u.exclusion_reason && ` (${u.exclusion_reason})`}
              </p>
            ))}
          </div>
        )}
        <form className="grid gap-2 sm:grid-cols-2" onSubmit={(e) => {
          e.preventDefault();
          setError("");
          const data = new FormData(e.currentTarget);
          createUnit.mutateAsync({
            name: String(data.get("name")), area_ha: Number(data.get("area_ha")),
            eligibility_status: eligibility,
            exclusion_reason: eligibility === "excluded" ? String(data.get("exclusion_reason")) : undefined,
          }).then(() => (e.target as HTMLFormElement).reset())
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to add unit"));
        }}>
          <TextInput name="name" placeholder="Unit name" required maxLength={200} />
          <TextInput name="area_ha" type="number" step="any" placeholder="Area (ha)" required min={0.01} />
          <Select value={eligibility} onChange={(e) => setEligibility(e.target.value)}>
            <option value="needs_review">Needs review</option>
            <option value="eligible">Eligible</option>
            <option value="excluded">Excluded</option>
          </Select>
          {eligibility === "excluded" && <TextInput name="exclusion_reason" placeholder="Exclusion reason (required)" required maxLength={2000} />}
          <div className="sm:col-span-2"><Button type="submit" loading={createUnit.isPending}>Add quantification unit</Button></div>
        </form>
      </Card>
    </div>
  );
}
