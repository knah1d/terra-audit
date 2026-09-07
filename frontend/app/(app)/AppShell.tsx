"use client";

import { Leaf, Menu, PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import { useState } from "react";
import { usePathname } from "next/navigation";
import { SidebarNav } from "./SidebarNav";
import { Sheet } from "@/components/ui/Sheet";
import type { SessionClaims } from "@/lib/session";

export function AppShell({ session, children }: { session: SessionClaims | null; children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileRoute, setMobileRoute] = useState<string | null>(null);
  const pathname = usePathname();
  return (
    <div className="min-h-screen p-3 md:flex md:gap-4 md:p-4">
      <a href="#main-content" className="glass-chrome-strong fixed left-4 top-4 z-50 -translate-y-32 rounded-xl p-3 focus:translate-y-0">Skip to content</a>
      <header className="glass-chrome-strong sticky top-3 z-chrome mb-5 flex items-center justify-between rounded-2xl px-4 py-3 md:hidden">
        <span className="flex items-center gap-2 font-semibold"><Leaf className="size-5 text-brand-600" />Terra Audit</span>
        <button type="button" aria-label="Open navigation" aria-expanded={mobileRoute === pathname} onClick={() => setMobileRoute(pathname)} className="glass-control rounded-xl p-2"><Menu className="size-5" /></button>
      </header>
      <aside className={`glass-chrome-strong sticky top-4 z-chrome hidden h-[calc(100dvh-2rem)] shrink-0 flex-col rounded-2xl p-3 transition-[width] duration-200 md:flex ${collapsed ? "w-20" : "w-64"}`}>
        <div className={`mb-7 flex items-center gap-2 px-1 pt-1 ${collapsed ? "flex-col" : ""}`}>
          <span className="glass-control flex size-9 shrink-0 items-center justify-center rounded-xl text-brand-700"><Leaf className="size-5" /></span>
          {!collapsed && <span className="flex-1 font-semibold tracking-tight">Terra Audit</span>}
          <button type="button" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)} className="liquid-hover rounded-lg p-2 text-text-secondary">
            {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
          </button>
        </div>
        <SidebarNav session={session} collapsed={collapsed} />
      </aside>
      <Sheet placement="drawer" open={mobileRoute === pathname} onClose={() => setMobileRoute(null)} title="Navigation">
        <button type="button" onClick={() => setMobileRoute(null)} aria-label="Close navigation" className="absolute right-4 top-4 rounded-lg p-2"><X className="size-4" /></button>
        <div className="flex min-h-80 flex-col gap-6" onClick={(event) => { if ((event.target as HTMLElement).closest("a")) setMobileRoute(null); }}><SidebarNav session={session} /></div>
      </Sheet>
      <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 px-1 py-3 outline-none sm:px-4 md:p-6">{children}</main>
    </div>
  );
}
