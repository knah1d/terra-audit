"use client";

import { Activity, MapPinned, LayoutList, BrainCircuit } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function ProjectTabs({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const options = [
    { href: `/projects/${projectId}/monitoring`, label: "Monitoring", icon: Activity },
    { href: `/projects/${projectId}/fields`, label: "Fields", icon: MapPinned },
    { href: `/projects/${projectId}/ai`, label: "AI workspace", icon: BrainCircuit },
    { href: `/reviews?project=${projectId}`, label: "Reviews", icon: LayoutList },
  ];
  return (
    <div className="flex gap-1 border-b border-border">
      {options.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
              active ? "border-brand-600 text-brand-700" : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            <Icon className="size-3.5" />
            {label}
          </Link>
        );
      })}
    </div>
  );
}
