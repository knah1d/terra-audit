"use client";

import { Users, Activity, MapPinned, LayoutList, BrainCircuit, ScrollText, LayoutDashboard } from "lucide-react";
import { revealNavigationItem } from "@/lib/reveal-navigation";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

export function ProjectTabs({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const nav = useRef<HTMLElement>(null);
  useEffect(() => { revealNavigationItem(nav.current, nav.current?.querySelector<HTMLElement>('[aria-current="page"]') ?? null); }, [pathname]);
  const options = [
    { href: `/projects/${projectId}/overview`, label: "Overview", icon: LayoutDashboard },
    { href: `/projects/${projectId}/monitoring`, label: "Monitoring", icon: Activity },
    { href: `/projects/${projectId}/fields`, label: "Fields", icon: MapPinned },
    { href: `/projects/${projectId}/methodology`, label: "Methodology", icon: ScrollText },
    { href: `/projects/${projectId}/members`, label: "Members", icon: Users },
    { href: `/projects/${projectId}/ai`, label: "AI workspace", icon: BrainCircuit },
    { href: `/reviews?project=${projectId}`, label: "Reviews", icon: LayoutList },
  ];
  return (
    <nav ref={nav} aria-label="Project sections" className="flex gap-1 overflow-x-auto border-b border-border-subtle">
      {options.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex min-h-11 shrink-0 items-center gap-2 rounded-t-lg border-b-2 px-3 text-sm font-medium ${
              active ? "border-brand-600 text-brand-700" : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            <Icon className="size-3.5" aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
