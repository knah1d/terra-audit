import "katex/dist/katex.min.css";
import { BlockMath } from "react-katex";
import { formatNumber } from "@/lib/format";

export type DerivationStep = {
  id: string;
  title: string;
  description?: string;
  formula?: string; // plain text/KaTeX-less for now — symbolic
  substitution?: string; // numeric substitution
  result: { label: string; value: number | null; unit: string };
  tone?: "neutral" | "warning" | "success";
};

const TONE_CLASSES: Record<string, string> = {
  neutral: "border-gray-200",
  warning: "border-amber-300 bg-amber-50",
  success: "border-emerald-300 bg-emerald-50",
};

function DerivationStepCard({ step, index, total }: { step: DerivationStep; index: number; total: number }) {
  return (
    <details
      className={`rounded-lg border p-4 ${TONE_CLASSES[step.tone ?? "neutral"]}`}
      open={index === 0}
    >
      <summary className="flex cursor-pointer items-center justify-between gap-4">
        <div>
          <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
            Step {index + 1} of {total}
          </span>
          <p className="font-medium">{step.title}</p>
        </div>
        <span className="whitespace-nowrap font-mono text-sm tabular-nums text-gray-700">
          {step.result.label}: {formatNumber(step.result.value, step.result.unit)} {step.result.unit}
        </span>
      </summary>
      <div className="mt-3 space-y-2 pl-1 text-sm text-gray-700">
        {step.description && <p>{step.description}</p>}
        {step.formula && (
          <div className="overflow-x-auto rounded bg-gray-50 px-2 py-1.5 text-sm">
            <BlockMath math={step.formula} errorColor="#dc2626" />
          </div>
        )}
        {step.substitution && (
          <div className="overflow-x-auto rounded bg-gray-50 px-2 py-1.5 text-sm text-gray-600">
            <BlockMath math={step.substitution} errorColor="#dc2626" />
          </div>
        )}
      </div>
    </details>
  );
}

/**
 * Deliberate credibility feature (see plan Part B5) — not a generic
 * key-value table. Calculation-specific step content is built by
 * LedgerRiceForm/LedgerAlmForm from the backend's result dict;
 * everything generic (rendering, collapsing, numeric formatting) lives
 * here, so a third methodology later reuses this untouched.
 */
export function DerivationTrail({ steps }: { steps: DerivationStep[] }) {
  return (
    <div className="flex flex-col gap-2">
      {steps.map((step, i) => (
        <DerivationStepCard key={step.id} step={step} index={i} total={steps.length} />
      ))}
    </div>
  );
}
