"use client";
import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/app/providers";
import { useProjectContext } from "@/components/projects/ProjectContext";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Select, TextInput } from "@/components/ui/Field";
import { useProjectMembers, useAddProjectMember } from "@/hooks/use-projects";
import { apiFetch } from "@/lib/api";
import { formatQueueTimestamp } from "@/lib/format";

export default function ProjectMembersPage() {
  const project = useProjectContext(); const session = useSession(); const client = useQueryClient();
  const members = useProjectMembers(project.project_id); const save = useAddProjectMember(project.project_id);
  const manage = session?.role === "admin" || (session?.role === "analyst" && members.data?.some(m => m.user_id === session.user_id && m.project_role === "lead"));
  const base = `/projects/${project.project_id}`;
  const candidates = useQuery({ queryKey: ["project-member-candidates", project.project_id], queryFn: () => apiFetch<{ user_id: string; email: string }[]>(`${base}/member-candidates`), enabled: !!manage });
  const [user, setUser] = useState(""); const [role, setRole] = useState("contributor"); const [reason, setReason] = useState(""); const toast = useToast();
  const remove = useMutation({ mutationFn: () => apiFetch(`${base}/members/${encodeURIComponent(user)}?reason=${encodeURIComponent(reason)}`, { method: "DELETE" }), onSuccess: () => client.invalidateQueries({ queryKey: ["project-members", project.project_id] }) });
  const busy = save.isPending || remove.isPending;
  const selected = members.data?.find(m => m.user_id === user);
  const selfLead = user === session?.user_id && selected?.project_role === "lead";
  return <div className="ui-container space-y-6">
    <Card><h2 className="ui-section-title mb-3">Project members</h2><p className="ui-secondary mb-4">Project access is separate from organization membership. Leads manage project workflows; contributors prepare evidence; viewers read project records. Organization permissions still apply.</p>
      {members.isLoading ? <p>Loading members…</p> : members.data?.map(m => <div key={m.user_id} className="flex flex-wrap justify-between gap-3 border-t border-border py-3"><div><p className="break-all">{m.email}</p><p className="ui-meta">Added {formatQueueTimestamp(m.added_at)}</p></div><span>{m.project_role}</span></div>)}
    </Card>
    {manage && <Card><h3 className="ui-subsection-title mb-3">Add or update a member</h3><form className="space-y-3" onSubmit={async e => {
      e.preventDefault();
      try { await save.mutateAsync({ user_id: user, project_role: role, reason }); toast.success("Project membership saved."); }
      catch (e) { toast.error(e, "Could not update member"); }
    }}><label className="ui-label">Organization user<Select required value={user} disabled={busy || candidates.isLoading} onChange={e => { setUser(e.target.value); setRole(members.data?.find(m => m.user_id === e.target.value)?.project_role ?? "contributor"); setReason(""); }}><option value="">Choose a user…</option>{candidates.data?.map(u => <option key={u.user_id} value={u.user_id}>{u.email}</option>)}</Select></label>
      <label className="ui-label">Project role<Select value={role} onChange={e => setRole(e.target.value)} disabled={busy || selfLead}><option value="lead">Lead</option><option value="contributor">Contributor</option><option value="viewer">Viewer</option></Select></label>
      {selfLead && <p className="ui-meta">Ask another lead or administrator to change your own lead access.</p>}
      <label className="ui-label">Reason<TextInput required minLength={5} maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} disabled={busy} /></label>
      <div className="flex flex-wrap gap-3"><Button type="submit" loading={save.isPending} disabled={busy || !user}>Save membership</Button>
      {selected && !selfLead && <Button type="button" variant="danger" disabled={busy || reason.trim().length < 5} onClick={async () => { if (!window.confirm(`Remove ${selected.email} from this project?`)) return; try { await remove.mutateAsync(); setUser(""); toast.success("Project access removed. Existing records are retained."); } catch (e) { toast.error(e, "Could not remove member"); } }}>Remove project access</Button>}
      </div></form></Card>}
    {(members.error || candidates.error) && <p role="alert" className="text-danger-700">{members.error?.message || candidates.error?.message}</p>}
  </div>;
}
