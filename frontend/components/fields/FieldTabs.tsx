"use client";

import { FlaskConical, Pencil, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

/** Link-based tab bar for the field-detail sub-nav — visually matches
 * components/ui/Tabs.tsx's segmented-control look, but each option is a
 * real route rather than local state. */
export function FieldTabs({ fieldId, fieldType }: { fieldId: string; fieldType: string }) {
  const pathname = usePathname();

  const options = [
    { href: `/fields/${fieldId}/ledger`, label: "Carbon Asset Ledger", icon: Wallet },
    ...(fieldType === "cropland_alm_vm0042"
      ? [{ href: `/fields/${fieldId}/practice-data`, label: "Practice & Soil Data", icon: FlaskConical }]
      : []),
    { href: `/fields/${fieldId}/edit`, label: "Edit", icon: Pencil },
  ];

  return (
    <div className="inline-flex gap-1 rounded-lg bg-surface-muted p-1 text-sm">
      {options.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={`press flex items-center gap-1.5 rounded-sm px-3 py-1.5 font-medium ${
              active
                ? "bg-surface text-text-primary shadow-xs"
                : "text-text-secondary hover:text-text-primary"
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
