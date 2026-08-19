"use client";

import { FlaskConical, Pencil, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Toolbar } from "@/components/ui/Toolbar";

/** Floating tab bar for the field-detail sub-nav — each option is a real
 * route rather than local state, but visually reads as one glass toolbar
 * (Apple Health/Wallet's tab-bar pattern) rather than a flat segmented
 * strip sitting inline in the page.
 *
 * The active pill is one shared element that slides between tabs
 * (measured via getBoundingClientRect, animated with a CSS transform)
 * rather than each Link independently toggling its own background —
 * the same "shared layout" effect a layoutId animation library would
 * give, done with a ref + one state update since there's exactly one
 * moving element and no gesture/physics involved. */
export function FieldTabs({ fieldId, fieldType }: { fieldId: string; fieldType: string }) {
  const pathname = usePathname();
  const containerRef = useRef<HTMLDivElement>(null);
  const [pillStyle, setPillStyle] = useState<{ left: number; width: number } | null>(null);

  const options = [
    { href: `/fields/${fieldId}/ledger`, label: "Carbon Asset Ledger", icon: Wallet },
    ...(fieldType === "cropland_alm_vm0042"
      ? [{ href: `/fields/${fieldId}/practice-data`, label: "Practice & Soil Data", icon: FlaskConical }]
      : []),
    { href: `/fields/${fieldId}/edit`, label: "Edit", icon: Pencil },
  ];

  useEffect(() => {
    function measure() {
      const container = containerRef.current;
      if (!container) return;
      const activeEl = container.querySelector<HTMLElement>('[data-active="true"]');
      if (!activeEl) {
        setPillStyle(null);
        return;
      }
      const containerRect = container.getBoundingClientRect();
      const elRect = activeEl.getBoundingClientRect();
      setPillStyle({ left: elRect.left - containerRect.left, width: elRect.width });
    }
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [pathname, fieldType]);

  return (
    <Toolbar className="relative mb-0 inline-flex w-fit gap-1 px-1.5 py-1.5">
      <div ref={containerRef} className="relative flex gap-1">
        {pillStyle && (
          <div
            aria-hidden
            className="absolute top-0 h-full rounded-full bg-brand-600 shadow-xs transition-[transform,width] duration-[var(--dur-base)] ease-[var(--curve-out)]"
            style={{ width: pillStyle.width, transform: `translateX(${pillStyle.left}px)` }}
          />
        )}
        {options.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              data-active={active}
              className={`press relative z-10 flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors duration-[var(--dur-base)] ${
                active ? "text-white" : "text-text-secondary hover:bg-surface-muted hover:text-text-primary"
              }`}
            >
              <Icon className="size-3.5" />
              {label}
            </Link>
          );
        })}
      </div>
    </Toolbar>
  );
}
