"use client";

import { formatDate } from "@/lib/format";
import Link from "next/link";
import { useState } from "react";
import { useProjectContext } from "@/components/projects/ProjectContext";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput } from "@/components/ui/Field";
import { useFields } from "@/hooks/use-fields";
import { useAssignFieldToProject, useChangeFieldMembershipStart, useEndFieldMembership, useProjectFields } from "@/hooks/use-projects";

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
  // One project per field at a time: only standalone fields can be assigned.
  const assignable = (fields.data ?? []).filter((f) => !assignedFieldIds.has(f.field_id) && !f.current_project);

  return (
    <div className="ui-container space-y-6">
      {error && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{error}</p>}
      <Card>
        <h3 className="ui-subsection-title mb-3">Assign an existing field</h3>
        <p className="ui-meta mb-3">
          Only standalone fields are listed — a field belongs to one project at a time. Its history is kept.{" "}
          <Link className="underline" href={`/fields/new?project=${encodeURIComponent(project.project_id)}`}>Register a new field for this project</Link>
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
                                 name={fields.data?.find(f => f.field_id === m.field_id)?.name ?? m.field_id} start={m.effective_start_date} onEnd={endMembership} projectId={project.project_id} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function EndMembershipRow({ membershipId, fieldId, name, start, onEnd, projectId }: {
  membershipId: string; fieldId: string; name: string; start: string;
  onEnd: ReturnType<typeof useEndFieldMembership>; projectId: string;
}) {
  const [reason, setReason] = useState("");
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const changeStart = useChangeFieldMembershipStart(projectId);
  const [editingStart, setEditingStart] = useState(false);
  const [newStart, setNewStart] = useState(start);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border py-2 text-sm first:border-t-0">
      <div>
        <Link className="underline" href={`/fields/${fieldId}/enrollment`}>{name}</Link> <span className="ui-meta">{fieldId}</span>
        <Badge tone="neutral" className="ml-2">since {formatDate(start)}</Badge>
        {!editingStart ? (
          <Button variant="ghost" size="sm" className="ml-1" onClick={() => setEditingStart(true)}>Change start date</Button>
        ) : (
          <form className="mt-2 flex flex-wrap items-center gap-2" onSubmit={(e) => {
            e.preventDefault();
            setError("");
            changeStart.mutateAsync({ membershipId, start: newStart }).then(() => setEditingStart(false))
              .catch((err) => setError(err instanceof Error ? err.message : "Could not change the start date"));
          }}>
            <TextInput aria-label="New start date" type="date" value={newStart} onChange={(e) => setNewStart(e.target.value)} required className="max-w-44" />
            <Button type="submit" size="sm" loading={changeStart.isPending}>Save</Button>
            <Button type="button" variant="secondary" size="sm" onClick={() => { setEditingStart(false); setNewStart(start); }}>Cancel</Button>
          </form>
        )}
        {error && <p role="alert" className="mt-1 text-danger-700">{error}</p>}
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
        </form>
      )}
    </div>
  );
}
