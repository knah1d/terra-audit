"use client";

import { Activity, BrainCircuit, ClipboardCheck, FolderKanban, LayoutGrid, Plus, Rows3, Users } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoutButton } from "@/components/fields/LogoutButton";
import { resetLiquidPointer, trackLiquidPointer } from "@/components/ui/liquid-pointer";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import type { SessionClaims } from "@/lib/session";

const NAV_ITEMS = [
  { href: "/projects", label: "Projects", icon: Rows3, exact: false },
  { href: "/fields", label: "Fields", icon: FolderKanban, exact: false },
  { href: "/fields/new", label: "Register a field", icon: Plus, exact: true },
  { href: "/portfolio", label: "Portfolio", icon: LayoutGrid, exact: false },
  { href: "/reviews", label: "Reviews", icon: ClipboardCheck, exact: false },
  { href: "/ai-validation", label: "AI Validation", icon: BrainCircuit, exact: false },
];

const ADMIN_NAV_ITEMS = [
  { href: "/admin/setup", label: "Product setup", icon: ClipboardCheck, exact: false },
  { href: "/team", label: "Team", icon: Users, exact: false },
  { href: "/admin/queue", label: "Worker & queue", icon: Activity, exact: false },
];

export function SidebarNav({ session, collapsed = false }: { session: SessionClaims | null; collapsed?: boolean }) {
  const pathname = usePathname();
  const items = session?.role === "admin" ? [...NAV_ITEMS, ...ADMIN_NAV_ITEMS] : NAV_ITEMS;

  // Non-exact items match by prefix (e.g. "/fields" matches
  // "/fields/{id}/ledger"), but that would also match "/fields/new" —
  // its own exact-match item. Picking the single longest matching href
  // (rather than letting each item decide "active" independently) makes
  // the more specific route win instead of both lighting up at once.
  const activeHref = items
    .filter(({ href, exact }) => (exact ? pathname === href : pathname === href || pathname.startsWith(`${href}/`)))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <>
      <nav className="flex flex-col gap-0.5 text-sm">
        {items.map(({ href, label, icon: Icon }) => {
          const active = href === activeHref;
          return (
            <Link
              key={href}
              href={href}
              title={collapsed ? label : undefined}
              aria-label={collapsed ? label : undefined}
              aria-current={active ? "page" : undefined}
              onPointerEnter={trackLiquidPointer}
              onPointerMove={trackLiquidPointer}
              onPointerLeave={resetLiquidPointer}
              className={`liquid-hover press flex items-center gap-2.5 rounded-xl px-3 py-3 font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 ${
                active ? "liquid-active text-brand-700" : "text-text-secondary hover:text-text-primary"
              }`}
            >
              <Icon className="size-4" />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Its own tinted card — a "control center" corner rather than
       * profile info + a toggle just sitting loose above the logout
       * button. */}
      <div className={`${collapsed ? "hidden" : "flex"} mt-auto flex-col gap-3 rounded-xl glass-control p-3`}>
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
