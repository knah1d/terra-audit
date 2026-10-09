"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import { usePathname } from "next/navigation";
import { ButtonLink } from "@/components/ui/Button";
import { fieldSteps } from "@/lib/field-steps";

/** Back / Next between the field's workflow steps (lib/field-steps.ts), so a
 * user can move through the steps in order without hunting in the tab bar.
 * Renders nothing on pages that are not a step (Edit, quick preview). */
export function StepNav({ fieldId, fieldType }: { fieldId: string; fieldType: string }) {
  const pathname = usePathname();
  const steps = fieldSteps(fieldType);
  const index = steps.findIndex((s) => pathname.endsWith(`/${s.segment}`));
  if (index === -1) return null;

  const numbered = steps.filter((s) => s.numbered);
  const current = steps[index];
  const position = numbered.indexOf(current) + 1;
  const prev = steps[index - 1];
  const next = steps[index + 1];
  const href = (segment: string) => `/fields/${encodeURIComponent(fieldId)}/${segment}`;

  return (
    <nav aria-label="Step navigation" className="ui-container mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-border-subtle pt-5">
      <div className="min-w-0">
        {prev && (
          <ButtonLink href={href(prev.segment)} variant="ghost" size="sm" icon={ArrowLeft}>
            {prev.label}
          </ButtonLink>
        )}
      </div>
      {position > 0 && (
        <p className="ui-meta order-first w-full text-center sm:order-none sm:w-auto">
          Step {position} of {numbered.length} · {current.label}
        </p>
      )}
      <div className="min-w-0">
        {next && (
          <ButtonLink href={href(next.segment)} variant={next.numbered ? "primary" : "secondary"} size="sm" className="flex-row-reverse gap-2" icon={ArrowRight}>
            {next.numbered ? `Next: ${next.label}` : next.label}
          </ButtonLink>
        )}
      </div>
    </nav>
  );
}
