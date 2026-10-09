"use client";
import { formatQueueTimestamp } from "@/lib/format";

import { UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { FieldLabel, Select, TextInput } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { RoleGate } from "@/components/ui/RoleGate";
import { Sheet } from "@/components/ui/Sheet";
import { Skeleton } from "@/components/ui/Skeleton";
import { useCreateTeamUser, useTeamUsers } from "@/hooks/use-team";
import type { UserRole } from "@/types/api";

const ROLES: UserRole[] = ["admin", "analyst", "viewer"];

function InviteSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [email, setEmail] = useState("");
  const [inviteUrl, setInviteUrl] = useState("");
  const [role, setRole] = useState<UserRole>("analyst");
  const toast = useToast();
  const create = useCreateTeamUser();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const result = await create.mutateAsync({ email, role });
      setInviteUrl(result.invitation_url);
    } catch (err) {
      toast.error(err, "Could not invite teammate");
    }
  }

  return (
    <Sheet open={open} onClose={() => { setInviteUrl(""); onClose(); }} title="Invite teammate">
      {inviteUrl && <div className="mb-4 space-y-2 text-sm"><p>Share this one-time invitation with {email}. It expires in 48 hours and is not emailed automatically.</p><TextInput aria-label="Invitation link" readOnly value={inviteUrl} onFocus={e => e.target.select()} /><p>The teammate chooses their own password. Add them to projects after they accept.</p></div>}
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div>
          <FieldLabel htmlFor="field-1">Email</FieldLabel>
          <TextInput id="field-1" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <FieldLabel htmlFor="field-2">Role</FieldLabel>
          <Select id="field-2" value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </Select>
        </div>
        <Button type="submit" loading={create.isPending} className="mt-1">
          Create invitation link
        </Button>
        <Button type="button" variant="secondary" onClick={() => { setInviteUrl(""); onClose(); }}>Cancel</Button>
      </form>
    </Sheet>
  );
}

export default function TeamPage() {
  const { data: users, isLoading } = useTeamUsers();
  const [inviting, setInviting] = useState(false);

  return (
    <RoleGate allow={["admin"]} fallback={<Alert tone="danger" title="Admins only">You don&apos;t have access to this page.</Alert>}>
      <div className="ui-container">
        <PageHeader
          title="Team"
          subtitle="Everyone with access to this organization."
          actions={<Button icon={UserPlus} size="sm" onClick={() => setInviting(true)}>Invite teammate</Button>}
        />

        {isLoading && <Skeleton className="h-64" />}

        {users && users.length === 0 && (
          <EmptyState icon={Users} title="No teammates yet" description="Invite a teammate to give them access." />
        )}

        {users && users.length > 0 && (
          <div className="ui-card overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="ui-meta text-left font-medium uppercase tracking-wide">
                  <th className="px-4 pb-2.5 pt-4">Email</th>
                  <th className="px-4 pb-2.5 pt-4">Role</th>
                  <th className="px-4 pb-2.5 pt-4">Active</th>
                  <th className="px-4 pb-2.5 pt-4">Last Login</th>
                  <th className="px-4 pb-2.5 pt-4">Created</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.user_id} className="border-t border-border/60">
                    <td className="px-4 py-3 text-text-primary">{u.email}</td>
                    <td className="px-4 py-3 capitalize text-text-secondary">{u.role}</td>
                    <td className="px-4 py-3 text-text-secondary">{u.is_active ? "Yes" : "No"}</td>
                    <td className="px-4 py-3 text-text-secondary">{u.last_login_at ? formatQueueTimestamp(u.last_login_at) : "Never"}</td>
                    <td className="px-4 py-3 text-text-secondary">{formatQueueTimestamp(u.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <InviteSheet open={inviting} onClose={() => setInviting(false)} />
      </div>
    </RoleGate>
  );
}
