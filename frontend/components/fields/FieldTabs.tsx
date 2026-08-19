"use client";

import { FlaskConical, Pencil, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Toolbar } from "@/components/ui/Toolbar";

/** Floating tab bar for the field-detail sub-nav — each option is a real
 * route rather than local state, but visually reads as one glass toolbar
 * (Apple Health/Wallet's tab-bar pattern) rather than a flat segmented
 * strip sitting inline in the page. */
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
    <Toolbar className="mb-0 inline-flex w-fit gap-1 px-1.5 py-1.5">
      {options.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={`press flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium ${
              active
                ? "bg-brand-600 text-white shadow-xs"
                : "text-text-secondary hover:bg-surface-muted hover:text-text-primary"
            }`}
          >
            <Icon className="size-3.5" />
            {label}
          </Link>
        );
      })}
    </Toolbar>
  );
}
