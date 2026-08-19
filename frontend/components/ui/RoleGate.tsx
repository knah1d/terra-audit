"use client";

import { useSession } from "@/app/providers";

/**
 * UX-only: disables/hides write actions for a viewer so they aren't
 * surprised by a rejected request. Real enforcement is 100% server-side
 * (backend/deps.py's require_roles) — this component never substitutes
 * for that, it only avoids a bad interaction for a role that would be
 * rejected anyway.
 */
export function RoleGate({
  allow,
  children,
  fallback = null,
}: {
  allow: Array<"admin" | "analyst" | "viewer">;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  const session = useSession();
  if (!session || !allow.includes(session.role)) {
    return <>{fallback}</>;
  }
  return <>{children}</>;
}
