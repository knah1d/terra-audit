"use client";

import { StatCard } from "@/components/ui/Card";
import { useCountUp } from "@/hooks/use-count-up";
import { formatNumber } from "@/lib/format";

/**
 * The Final Issuance figure ticks up from its previous value instead of
 * snapping — this is the single number in the whole ledger a user's eye
 * should land on after a calculation, so it gets the one animated-number
 * treatment in the app rather than sprinkling it everywhere.
 */
export function FinalIssuanceStat({ value }: { value: number | null }) {
  // useCountUp needs a real number to animate toward; null (the blocked/
  // not-yet-computed case) just renders "—" via formatNumber, unanimated.
  const animated = useCountUp(value ?? 0);
  return (
    <StatCard
      label="Final Issuance"
      value={`${formatNumber(value === null ? null : animated, "tco2e")} tCO2e`}
      tone="success"
    />
  );
}
