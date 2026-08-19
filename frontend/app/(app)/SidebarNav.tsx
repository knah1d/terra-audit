"use client";

import { FolderKanban, Plus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoutButton } from "@/components/fields/LogoutButton";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import type { SessionClaims } from "@/lib/session";

const NAV_ITEMS = [
  { href: "/fields", label: "Fields", icon: FolderKanban, exact: false },
  { href: "/fields/new", label: "Register a field", icon: Plus, exact: true },
];

export function SidebarNav({ session }: { session: SessionClaims | null }) {
  const pathname = usePathname();

  return (
    <>
      <nav className="flex flex-col gap-0.5 text-sm">
        {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => {
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

      <div className="mt-auto flex flex-col gap-3 border-t border-border pt-4">
        <div className="flex items-center justify-between px-1">
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
