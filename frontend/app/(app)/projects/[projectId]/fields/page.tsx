"use client";

import { formatDate } from "@/lib/format";
import Link from "next/link";
import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { useProjectContext } from "@/components/projects/ProjectContext";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
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
  const toast = useToast();

  const openMemberships = (memberships.data ?? []).filter((m) => m.removed_at === null);
  const assignedFieldIds = new Set(openMemberships.map((m) => m.field_id));
  // One project per field at a time: only standalone fields can be assigned.
  const assignable = (fields.data ?? []).filter((f) => !assignedFieldIds.has(f.field_id) && !f.current_project);

  return (
    <div className="ui-container space-y-6">
      {project.can_manage && <Card>
        <h3 className="ui-subsection-title mb-3">Assign an existing field</h3>
        <p className="ui-meta mb-3">
          Only standalone fields are listed — a field belongs to one project at a time. Its history is kept.{" "}
          <Link className="underline" href={`/fields/new?project=${encodeURIComponent(project.project_id)}`}>Register a new field for this project</Link>
        </p>
        <form className="grid grid-cols-1 items-end gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]" onSubmit={(e) => {
          e.preventDefault();
          assign.mutateAsync({ field_id: fieldId, effective_start_date: effectiveDate }).then(() => { setFieldId(""); toast.success("Field assigned"); })
            .catch((err) => toast.error(err, "Failed to assign field"));
        }}>
          <label className="ui-label flex min-w-0 flex-col gap-2">Field to assign
          <Select aria-label="Field to assign" value={fieldId} onChange={(e) => setFieldId(e.target.value)} required>
            <option value="">Choose a field…</option>
            {assignable.map((f) => <option key={f.field_id} value={f.field_id}>{f.name}{f.district ? ` · ${f.district}` : ""}</option>)}
          </Select>
          </label>
          <label className="ui-label flex min-w-0 flex-col gap-2">In the project from<TextInput type="date" required value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)} /></label>
          <Button type="submit" loading={assign.isPending} className="h-[var(--control-h)]">Assign to project</Button>
        </form>
      </Card>}

      <Card>
        <h3 className="ui-subsection-title mb-3">Fields in this project</h3>
        {memberships.isLoading ? <Skeleton className="h-24" /> : memberships.error ? (
          <Alert tone="danger" title="Could not load this project's fields">{memberships.error.message}</Alert>
        ) : !openMemberships.length ? <p className="ui-secondary">No fields assigned yet.</p> : (
          <div className="space-y-2">
            {openMemberships.map((m) => (
              <EndMembershipRow key={m.membership_id} membershipId={m.membership_id} fieldId={m.field_id}
                                 name={fields.data?.find(f => f.field_id === m.field_id)?.name ?? m.field_id} start={m.effective_start_date} onEnd={endMembership} projectId={project.project_id}
                                 canManage={project.can_manage} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

const todayIso = () => new Date().toISOString().slice(0, 10);

function EndMembershipRow({ membershipId, fieldId, name, start, onEnd, projectId, canManage }: {
  membershipId: string; fieldId: string; name: string; start: string;
  onEnd: ReturnType<typeof useEndFieldMembership>; projectId: string; canManage: boolean;
}) {
  const [reason, setReason] = useState("");
  const [end, setEnd] = useState(todayIso);
  const [open, setOpen] = useState(false);
  const toast = useToast();
  const changeStart = useChangeFieldMembershipStart(projectId);
  const [editingStart, setEditingStart] = useState(false);
  const [newStart, setNewStart] = useState(start);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border py-2 text-sm first:border-t-0">
      <div>
        <Link className="font-medium underline" href={`/fields/${encodeURIComponent(fieldId)}/overview`}>{name}</Link>
        <Badge tone="neutral" className="ml-2">since {formatDate(start)}</Badge>
        {!canManage ? null : !editingStart ? (
          <Button variant="ghost" size="sm" className="ml-1" onClick={() => setEditingStart(true)}>Change start date</Button>
        ) : (
          <form className="mt-2 flex flex-wrap items-center gap-2" onSubmit={(e) => {
            e.preventDefault();
            changeStart.mutateAsync({ membershipId, start: newStart }).then(() => { setEditingStart(false); toast.success("Start date updated"); })
              .catch((err) => toast.error(err, "Could not change the start date"));
          }}>
            <TextInput aria-label="New start date" type="date" value={newStart} onChange={(e) => setNewStart(e.target.value)} required className="max-w-44" />
            <Button type="submit" size="sm" loading={changeStart.isPending}>Save</Button>
            <Button type="button" variant="secondary" size="sm" onClick={() => { setEditingStart(false); setNewStart(start); }}>Cancel</Button>
          </form>
        )}
      </div>
      {!canManage ? null : !open ? (
        <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>Remove from project</Button>
      ) : (
        <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => {
          e.preventDefault();
          onEnd.mutateAsync({ membershipId, reason, end }).then(() => { setOpen(false); toast.success("Field removed from the project", { description: "Its history is kept." }); })
            .catch(e => toast.error(e, "Could not remove the field"));
        }}>
          <label className="ui-meta">Last day in project
            <TextInput aria-label="Last day in the project" type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} required className="max-w-44" />
          </label>
          <TextInput aria-label="Reason for removing the field" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason" required className="max-w-xs" />
          <Button type="submit" variant="danger" size="sm" loading={onEnd.isPending}>Confirm</Button>
          <Button type="button" variant="secondary" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
          <p className="ui-meta w-full">The field can join another project from the day after its last day here.</p>
        </form>
      )}
    </div>
  );
}
