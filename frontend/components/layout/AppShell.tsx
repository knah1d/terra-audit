"use client";

import { Leaf, Menu, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { SidebarNav } from "./SidebarNav";
import { Sheet } from "@/components/ui/Sheet";
import type { SessionClaims } from "@/lib/session";

export function AppShell({ session, children }: { session: SessionClaims | null; children: React.ReactNode }) {
  const [mobileRoute, setMobileRoute] = useState<string | null>(null);
  const pathname = usePathname();
  // Inside a field or project workspace (pages with their own tab bar) the
  // sidebar shrinks to icons to give the workspace room; it expands again on
  // top-level pages. A manual toggle holds until the user moves between the two.
  const inWorkspace = /^\/(fields|projects)\/[^/]+\/./.test(pathname);
  const [override, setOverride] = useState<{ inWorkspace: boolean; collapsed: boolean } | null>(null);
  const collapsed = override?.inWorkspace === inWorkspace ? override.collapsed : inWorkspace;
  const setCollapsed = (value: boolean) => setOverride({ inWorkspace, collapsed: value });
  return (
    <div className="min-h-screen p-3 lg:flex lg:gap-4 lg:p-4">
      <a href="#main-content" className="glass-chrome-strong fixed left-4 top-4 z-50 -translate-y-32 rounded-xl p-3 focus:translate-y-0">Skip to content</a>
      <header className="glass-chrome-strong sticky top-3 z-chrome mb-4 flex items-center justify-between rounded-xl px-4 py-2 lg:hidden">
        <span className="flex items-center gap-2 font-semibold"><Leaf className="size-5 text-brand-600" />Terra Audit</span>
        <button type="button" aria-label="Open navigation" aria-expanded={mobileRoute === pathname} onClick={() => setMobileRoute(pathname)} className="glass-control flex size-11 items-center justify-center rounded-lg"><Menu className="size-5" /></button>
      </header>
      <aside className={`glass-chrome-strong sticky top-4 z-chrome hidden h-[calc(100dvh-2rem)] shrink-0 flex-col rounded-2xl p-3 transition-[width] duration-200 lg:flex ${collapsed ? "w-20" : "w-64"}`}>
        <div className={`mb-6 flex items-center gap-2 px-1 pt-1 ${collapsed ? "flex-col" : ""}`}>
          <span className="glass-control flex size-9 shrink-0 items-center justify-center rounded-xl text-brand-700"><Leaf className="size-5" /></span>
          {!collapsed && <span className="flex-1 font-semibold tracking-tight">Terra Audit</span>}
          <button type="button" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)} className="liquid-hover flex size-9 items-center justify-center rounded-lg text-text-secondary">
            {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
          </button>
        </div>
        <SidebarNav session={session} collapsed={collapsed} />
      </aside>
      <Sheet placement="drawer" open={mobileRoute === pathname} onClose={() => setMobileRoute(null)} title="Navigation">
        <div className="flex min-h-80 flex-col gap-6" onClick={(event) => { if ((event.target as HTMLElement).closest("a")) setMobileRoute(null); }}><SidebarNav session={session} /></div>
      </Sheet>
      <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 px-1 py-4 outline-none sm:px-4 lg:px-8 lg:py-6">{children}</main>
    </div>
  );
}
