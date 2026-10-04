"use client";

import Link from "next/link";
import { useState } from "react";
import { useProjectContext } from "@/components/projects/ProjectContext";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput } from "@/components/ui/Field";
import { useFields } from "@/hooks/use-fields";
import { useAssignFieldToProject, useEndFieldMembership, useProjectFields } from "@/hooks/use-projects";

export default function ProjectFieldsPage() {
  const project = useProjectContext();
  const fields = useFields();
  const memberships = useProjectFields(project.project_id);
  const assign = useAssignFieldToProject(project.project_id);
  const endMembership = useEndFieldMembership(project.project_id);
  const [fieldId, setFieldId] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [error, setError] = useState("");

  const openMemberships = (memberships.data ?? []).filter((m) => m.removed_at === null);
  const assignedFieldIds = new Set(openMemberships.map((m) => m.field_id));
  const assignable = (fields.data ?? []).filter((f) => !assignedFieldIds.has(f.field_id));

  return (
    <div className="ui-container space-y-6">
      {error && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{error}</p>}
      <Card>
        <h3 className="ui-subsection-title mb-3">Assign an existing field</h3>
        <p className="ui-meta mb-3">
          This never guesses an assignment or touches the field&apos;s history — it only records that this field
          is part of this project as of the effective date below. A field can belong to more than one project at once.
        </p>
        <form className="flex flex-wrap gap-2" onSubmit={(e) => {
          e.preventDefault();
          setError("");
          assign.mutateAsync({ field_id: fieldId, effective_start_date: effectiveDate }).then(() => setFieldId(""))
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to assign field"));
        }}>
          <Select aria-label="Field to assign" value={fieldId} onChange={(e) => setFieldId(e.target.value)} required className="max-w-xs">
            <option value="">Choose a field…</option>
            {assignable.map((f) => <option key={f.field_id} value={f.field_id}>{f.name} ({f.field_id})</option>)}
          </Select>
          <label className="ui-label">Effective start date<TextInput type="date" required value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)} /></label>
          <Button type="submit" loading={assign.isPending}>Assign to project</Button>
        </form>
      </Card>

      <Card>
        <h3 className="ui-subsection-title mb-3">Fields in this project</h3>
        {!openMemberships.length ? <p className="ui-secondary">No fields assigned yet.</p> : (
          <div className="space-y-2">
            {openMemberships.map((m) => (
              <EndMembershipRow key={m.membership_id} membershipId={m.membership_id} fieldId={m.field_id}
                                 name={fields.data?.find(f => f.field_id === m.field_id)?.name ?? m.field_id} start={m.effective_start_date} onEnd={endMembership} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function EndMembershipRow({ membershipId, fieldId, name, start, onEnd }: {
  membershipId: string; fieldId: string; name: string; start: string;
  onEnd: ReturnType<typeof useEndFieldMembership>;
}) {
  const [reason, setReason] = useState("");
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border py-2 text-sm first:border-t-0">
      <div>
        <Link className="underline" href={`/fields/${fieldId}/enrollment`}>{name}</Link> <span className="ui-meta">{fieldId}</span>
        <Badge tone="neutral" className="ml-2">since {start}</Badge>
      </div>
      {!open ? (
        <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>End membership</Button>
      ) : (
        <form className="flex gap-2" onSubmit={(e) => {
          e.preventDefault();
          setError("");
          onEnd.mutateAsync({ membershipId, reason }).then(() => setOpen(false)).catch(e => setError(e instanceof Error ? e.message : "Could not end membership"));
        }}>
          <TextInput aria-label="Reason for ending membership" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason" required className="max-w-xs" />
          <Button type="submit" variant="danger" size="sm" loading={onEnd.isPending}>Confirm</Button>
          <Button type="button" variant="secondary" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
          {error && <p role="alert">{error}</p>}
        </form>
      )}
    </div>
  );
}
