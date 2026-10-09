"use client";

import { Paperclip, Calculator, ChevronRight, ClipboardList, FlaskConical, LayoutDashboard, Microscope, Satellite, ShieldCheck, Sprout, Wheat, type LucideIcon } from "lucide-react";
import { Fragment } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { resetLiquidPointer, trackLiquidPointer } from "@/components/ui/liquid-pointer";
import { revealNavigationItem } from "@/lib/reveal-navigation";
import { Toolbar } from "@/components/ui/Toolbar";
import { StepStatusDot } from "@/components/fields/StepStatusBadge";
import { useFieldWorkflow } from "@/hooks/use-workflow";
import { fieldSteps } from "@/lib/field-steps";

const STEP_ICONS: Record<string, LucideIcon> = {
  overview: LayoutDashboard,
  "crop-seasons": Sprout,
  enrollment: ClipboardList,
  "signal-analytics": Satellite,
  "awd-validation": ShieldCheck,
  calculations: Calculator,
  "practice-data": FlaskConical,
  "soil-evidence": Microscope,
  "production-records": Wheat,
  "evidence-files": Paperclip,
};

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

  // Workflow order lives in lib/field-steps.ts (shared with every redirect into a field).
  const workflow = useFieldWorkflow(fieldId);
  let stepNumber = 0;
  const options = fieldSteps(fieldType).map((step) => ({
    href: `/fields/${fieldId}/${step.segment}`,
    label: step.label,
    icon: STEP_ICONS[step.segment] ?? Paperclip,
    number: step.numbered ? ++stepNumber : null,
    status: workflow.data?.steps[step.segment]?.status,
  }));

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
    revealNavigationItem(containerRef.current?.parentElement ?? null, containerRef.current?.querySelector<HTMLElement>('[data-active="true"]') ?? null);
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [pathname, fieldType]);

  return (
    <Toolbar className="relative mb-0 inline-flex max-w-full w-fit overflow-x-auto gap-1 px-1.5 py-1.5">
      <div ref={containerRef} role="navigation" aria-label="Field sections" className="relative flex shrink-0 gap-1">
        {pillStyle && (
          // The sliding lens itself is glass, not a flat solid fill — a
          // brand-tinted .liquid-active-bg with the same specular rim the
          // per-item .liquid-hover material uses, so it reads as "one
          // piece of glass sliding between positions" rather than a
          // colored rectangle.
          <div
            aria-hidden
            className="absolute top-0 h-full rounded-full transition-[transform,width] duration-[var(--dur-base)] ease-[var(--curve-out)]"
            style={{
              width: pillStyle.width,
              transform: `translateX(${pillStyle.left}px)`,
              background: "var(--liquid-active-bg)",
              boxShadow:
                "inset 0 1px 0 var(--glass-specular), inset 0 0 0 1px var(--glass-rim), inset 0 0 0 1px color-mix(in srgb, var(--brand-600) 30%, transparent)",
            }}
          />
        )}
        {options.map(({ href, label, icon: Icon, number, status }, i) => {
          const active = pathname === href;
          return (
            <Fragment key={href}>
            {/* Arrow between consecutive numbered steps shows the order to follow. */}
            {i > 0 && number !== null && (
              <ChevronRight aria-hidden className="size-3.5 shrink-0 self-center text-text-tertiary" />
            )}
            <Link
              href={href}
              data-active={active}
              aria-current={active ? "page" : undefined}
              onPointerEnter={trackLiquidPointer}
              onPointerMove={trackLiquidPointer}
              onPointerLeave={resetLiquidPointer}
              className={`liquid-hover press relative z-10 flex min-h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-full px-3.5 text-sm font-medium transition-colors duration-[var(--dur-base)] ${
                active ? "text-brand-700" : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {number !== null ? (
                <span aria-hidden className="flex size-5 items-center justify-center rounded-full border border-current text-[0.7rem] tabular-nums">
                  {number}
                </span>
              ) : (
                <Icon className="size-3.5" aria-hidden />
              )}
              <span>{number !== null && <span className="sr-only">Step {number}: </span>}{label}</span>
              {status && <StepStatusDot status={status} />}
            </Link>
            </Fragment>
          );
        })}
      </div>
    </Toolbar>
  );
}
