"use client";

import { UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorText, FieldLabel, Select, TextInput } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { RoleGate } from "@/components/ui/RoleGate";
import { Sheet } from "@/components/ui/Sheet";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError } from "@/lib/api";
import { useCreateTeamUser, useTeamUsers } from "@/hooks/use-team";
import type { UserRole } from "@/types/api";

const ROLES: UserRole[] = ["admin", "analyst", "viewer"];

function InviteSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("analyst");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateTeamUser();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await create.mutateAsync({ email, password, role });
      setEmail("");
      setPassword("");
      setRole("analyst");
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not invite teammate");
    }
  }

  return (
    <Sheet open={open} onClose={onClose} title="Invite teammate">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div>
          <FieldLabel>Email</FieldLabel>
          <TextInput type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <FieldLabel>Temporary password</FieldLabel>
          <TextInput type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <div>
          <FieldLabel>Role</FieldLabel>
          <Select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </Select>
        </div>
        <ErrorText>{error ?? undefined}</ErrorText>
        <Button type="submit" loading={create.isPending} className="mt-1">
          Send invite
        </Button>
      </form>
    </Sheet>
  );
}

export default function TeamPage() {
  const { data: users, isLoading } = useTeamUsers();
  const [inviting, setInviting] = useState(false);

  return (
    <RoleGate allow={["admin"]} fallback={<Alert tone="danger" title="Admins only">You don&apos;t have access to this page.</Alert>}>
      <div className="mx-auto max-w-3xl">
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
          <div className="surface-card overflow-x-auto rounded-xl">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-medium uppercase tracking-wide text-text-tertiary">
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
                    <td className="px-4 py-3 text-text-secondary">{u.last_login_at ?? "Never"}</td>
                    <td className="px-4 py-3 text-text-secondary">{u.created_at ?? "—"}</td>
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
