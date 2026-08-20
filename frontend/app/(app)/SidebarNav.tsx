"use client";

import { BrainCircuit, FolderKanban, LayoutGrid, Plus, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoutButton } from "@/components/fields/LogoutButton";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import type { SessionClaims } from "@/lib/session";

const NAV_ITEMS = [
  { href: "/fields", label: "Fields", icon: FolderKanban, exact: false },
  { href: "/fields/new", label: "Register a field", icon: Plus, exact: true },
  { href: "/portfolio", label: "Portfolio", icon: LayoutGrid, exact: false },
  { href: "/ai-validation", label: "AI Validation", icon: BrainCircuit, exact: false },
];

const ADMIN_NAV_ITEMS = [
  { href: "/team", label: "Team", icon: Users, exact: false },
];

export function SidebarNav({ session }: { session: SessionClaims | null }) {
  const pathname = usePathname();
  const items = session?.role === "admin" ? [...NAV_ITEMS, ...ADMIN_NAV_ITEMS] : NAV_ITEMS;

  return (
    <>
      <nav className="flex flex-col gap-0.5 text-sm">
        {items.map(({ href, label, icon: Icon, exact }) => {
          const active = exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={`press flex items-center gap-2.5 rounded-full px-3 py-2 font-medium ${
                active
                  ? "bg-brand-50 text-brand-700"
                  : "text-text-secondary hover:bg-surface-muted hover:text-text-primary"
              }`}
            >
              <Icon className="size-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Its own tinted card — a "control center" corner rather than
       * profile info + a toggle just sitting loose above the logout
       * button. */}
      <div className="mt-auto flex flex-col gap-3 rounded-xl bg-surface-muted/60 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            {session && (
              <>
                <p className="truncate text-sm font-medium text-text-primary">{session.email}</p>
                <p className="text-xs capitalize text-text-tertiary">{session.role}</p>
              </>
            )}
          </div>
          <ThemeToggle />
        </div>
        <LogoutButton />
      </div>
    </>
  );
}
