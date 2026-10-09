"use client";

import { Activity, BrainCircuit, ClipboardCheck, FolderKanban, LayoutDashboard, LayoutGrid, Rows3, Settings, Users, CircleUserRound } from "lucide-react";
import Link from "next/link";
import { Fragment } from "react";
import { usePathname } from "next/navigation";
import { LogoutButton } from "@/components/auth/LogoutButton";
import { resetLiquidPointer, trackLiquidPointer } from "@/components/ui/liquid-pointer";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { useOrgSummary } from "@/hooks/use-projects";
import type { SessionClaims } from "@/lib/session";

// Field-specific work (crop seasons, analytics, calculations, evidence) lives
// inside each field's workspace, not here. "Register a field" is a button on
// the Fields page and the Dashboard.
const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: false },
  { href: "/projects", label: "Projects", icon: Rows3, exact: false },
  { href: "/fields", label: "Fields", icon: FolderKanban, exact: false },
  { href: "/portfolio", label: "Portfolio", icon: LayoutGrid, exact: false },
  { href: "/reviews", label: "Reviews", icon: ClipboardCheck, exact: false },
  { href: "/ai-validation", label: "AI Validation", icon: BrainCircuit, exact: false },
];

const ADMIN_NAV_ITEMS = [
  { href: "/admin/setup", label: "Product setup", icon: Settings, exact: false },
  { href: "/team", label: "Team", icon: Users, exact: false },
  { href: "/admin/queue", label: "Worker & queue", icon: Activity, exact: false },
];

export function SidebarNav({ session, collapsed = false }: { session: SessionClaims | null; collapsed?: boolean }) {
  const pathname = usePathname();
  const isAdmin = session?.role === "admin";
  // The first-run welcome page shows only the account card (email, role,
  // theme, logout) — no navigation until the organisation has a project or field.
  const summary = useOrgSummary();
  const onWelcome = pathname === "/dashboard" && (summary.isLoading || !!summary.data?.is_new_organization);
  const items = onWelcome ? [] : isAdmin ? [...NAV_ITEMS, ...ADMIN_NAV_ITEMS] : NAV_ITEMS;

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
      <nav className="flex flex-col gap-1 text-sm">
        {items.map(({ href, label, icon: Icon }) => {
          const active = href === activeHref;
          return (
            <Fragment key={href}>
            {/* Admin pages are grouped under their own heading. */}
            {isAdmin && href === ADMIN_NAV_ITEMS[0].href && (
              collapsed
                ? <hr className="my-2 border-border-subtle" />
                : <p className="ui-meta mt-4 px-3 pb-1 font-semibold uppercase tracking-wide">Administration</p>
            )}
            <Link
              href={href}
              title={collapsed ? label : undefined}
              aria-label={collapsed ? label : undefined}
              aria-current={active ? "page" : undefined}
              onPointerEnter={trackLiquidPointer}
              onPointerMove={trackLiquidPointer}
              onPointerLeave={resetLiquidPointer}
              className={`liquid-hover press flex min-h-11 items-center gap-3 rounded-lg px-3 font-medium ${
                active ? "liquid-active text-brand-700" : "text-text-secondary hover:text-text-primary"
              }`}
            >
              <Icon className="size-4" />
              {!collapsed && <span>{label}</span>}
            </Link>
            </Fragment>
          );
        })}
      </nav>

      {/* Its own tinted card — a "control center" corner rather than
       * profile info + a toggle just sitting loose above the logout
       * button. */}
      {collapsed ? <details className="relative mt-auto">
        <summary aria-label="Account and appearance" className="glass-control flex size-11 list-none items-center justify-center rounded-lg"><CircleUserRound className="size-5" /></summary>
        <div className="glass-chrome-strong absolute bottom-0 left-full ml-3 flex w-64 flex-col gap-3 rounded-xl p-4">
          <p className="truncate ui-label">{session?.email}</p>
          <ThemeToggle />
          <LogoutButton />
        </div>
      </details> : <div className="mt-auto flex flex-col gap-3 rounded-lg glass-control p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-text-primary">{session?.email}</p>
            <p className="ui-meta capitalize">{session?.role}</p>
          </div>
          <ThemeToggle />
        </div>
        <LogoutButton />
      </div>}

    </>
  );
}
