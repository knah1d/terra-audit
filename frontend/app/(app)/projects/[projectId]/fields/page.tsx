"use client";

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
  const [error, setError] = useState("");

  const openMemberships = (memberships.data ?? []).filter((m) => m.removed_at === null);
  const assignedFieldIds = new Set(openMemberships.map((m) => m.field_id));
  const assignable = (fields.data ?? []).filter((f) => !assignedFieldIds.has(f.field_id));

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      {error && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{error}</p>}
      <Card>
        <h3 className="mb-3 font-medium">Assign an existing field</h3>
        <p className="mb-3 text-xs text-text-tertiary">
          This never guesses an assignment or touches the field&apos;s history — it only records that this field
          is part of this project as of the effective date below. A field can belong to more than one project at once.
        </p>
        <form className="flex flex-wrap gap-2" onSubmit={(e) => {
          e.preventDefault();
          setError("");
          assign.mutateAsync({ field_id: fieldId }).then(() => setFieldId(""))
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to assign field"));
        }}>
          <Select value={fieldId} onChange={(e) => setFieldId(e.target.value)} required className="max-w-xs">
            <option value="">Choose a field…</option>
            {assignable.map((f) => <option key={f.field_id} value={f.field_id}>{f.name} ({f.field_id})</option>)}
          </Select>
          <Button type="submit" loading={assign.isPending}>Assign to project</Button>
        </form>
      </Card>

      <Card>
        <h3 className="mb-3 font-medium">Fields in this project</h3>
        {!openMemberships.length ? <p className="text-sm text-text-secondary">No fields assigned yet.</p> : (
          <div className="space-y-2">
            {openMemberships.map((m) => (
              <EndMembershipRow key={m.membership_id} membershipId={m.membership_id} fieldId={m.field_id}
                                 start={m.effective_start_date} onEnd={endMembership} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function EndMembershipRow({ membershipId, fieldId, start, onEnd }: {
  membershipId: string; fieldId: string; start: string;
  onEnd: ReturnType<typeof useEndFieldMembership>;
}) {
  const [reason, setReason] = useState("");
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border py-2 text-sm first:border-t-0">
      <div>
        <span className="font-mono">{fieldId}</span>
        <Badge tone="neutral" className="ml-2">since {start}</Badge>
      </div>
      {!open ? (
        <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>End membership</Button>
      ) : (
        <form className="flex gap-2" onSubmit={(e) => {
          e.preventDefault();
          onEnd.mutateAsync({ membershipId, reason }).then(() => setOpen(false));
        }}>
          <TextInput value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason" required className="max-w-xs" />
          <Button type="submit" variant="danger" size="sm" loading={onEnd.isPending}>Confirm</Button>
        </form>
      )}
    </div>
  );
}
