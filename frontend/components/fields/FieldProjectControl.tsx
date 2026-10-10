"use client";

import { FolderPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { useSession } from "@/app/providers";
import { NewProjectSheet } from "@/components/projects/NewProjectSheet";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select, TextInput } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useAssignFieldToProject, useProjects } from "@/hooks/use-projects";
import type { CurrentProject } from "@/types/api";

const today = () => new Date().toISOString().slice(0, 10);

/** Shows the field's current project (one at a time) or "Standalone", and
 * lets a standalone field join a project — same field, all history kept. */
export function FieldProjectControl({ fieldId, project }: { fieldId: string; project: CurrentProject | null }) {
  const router = useRouter();
  const session = useSession();
  const toast = useToast();
  const projects = useProjects();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [start, setStart] = useState(today);
  const [busy, setBusy] = useState(false);
  const assignToProject = useAssignFieldToProject(projectId || undefined);
  const canEdit = session?.role === "admin" || session?.role === "analyst";

  async function assign() {
    setBusy(true);
    try {
      // The shared hook refreshes every project and field view.
      await assignToProject.mutateAsync({ field_id: fieldId, effective_start_date: start });
      setOpen(false);
      toast.success("Added to project");
      router.refresh();
    } catch (err) {
      toast.error(err, "Couldn't add to project");
    } finally {
      setBusy(false);
    }
  }

  if (project) {
    return (
      <Link href={`/projects/${encodeURIComponent(project.project_id)}`}>
        <Badge tone="brand">Project: {project.name}</Badge>
      </Link>
    );
  }
  return (
    <>
      <Badge tone="neutral">Standalone</Badge>
      {canEdit && <Button size="sm" variant="ghost" icon={FolderPlus} onClick={() => setOpen(true)}>Add to project</Button>}
      <Sheet open={open} onClose={() => setOpen(false)} title="Add to a project">
        <div className="flex flex-col gap-3">
          <label className="text-sm">Project
            <Select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">Select a project</option>
              {/* Only projects where the user may add fields (lead/admin). */}
              {(projects.data ?? []).filter((p) => p.can_manage).map((p) => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
            </Select>
          </label>
          <Button type="button" variant="ghost" size="sm" onClick={() => setCreating(true)}>+ Create a new project</Button>
          <label className="text-sm">In the project from
            <TextInput type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </label>
          <Button loading={busy} disabled={!projectId || !start} onClick={() => void assign()}>Add to project</Button>
          <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
        </div>
      </Sheet>
      <NewProjectSheet open={creating} onClose={() => setCreating(false)} onCreated={(p) => setProjectId(p.project_id)} />
    </>
  );
}
