"use client";

import { LayoutGrid } from "lucide-react";
import Link from "next/link";
import { PortfolioBarChart } from "@/components/portfolio/PortfolioBarChart";
import { Button } from "@/components/ui/Button";
import { StatCard } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconTile } from "@/components/ui/IconTile";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { usePortfolio } from "@/hooks/use-portfolio";
import { formatNumber } from "@/lib/format";

const FIELD_TYPE_LABELS: Record<string, string> = {
  rice_awd: "Rice — AWD (VM0051)",
  cropland_alm_vm0042: "Cropland — ALM (VM0042)",
};

export default function PortfolioPage() {
  const { data: entries, isLoading } = usePortfolio();

  const registeredFields = entries?.length ?? 0;
  const totalArea = entries?.reduce((sum, e) => sum + (e.area_ha ?? 0), 0) ?? 0;
  const riceCredits = entries
    ?.filter((e) => e.field_type === "rice_awd" && e.final_issuance !== null)
    .reduce((sum, e) => sum + (e.final_issuance as number), 0) ?? 0;
  const almCredits = entries
    ?.filter((e) => e.field_type === "cropland_alm_vm0042" && e.final_issuance !== null)
    .reduce((sum, e) => sum + (e.final_issuance as number), 0) ?? 0;

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Portfolio" subtitle="Aggregated carbon-credit position across every registered field." />

      {isLoading && (
        <div className="grid gap-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-64" />
        </div>
      )}

      {entries && entries.length === 0 && (
        <EmptyState
          icon={LayoutGrid}
          title="No fields registered yet"
          description="Register a field to start tracking its carbon-credit position here."
          action={
            <Link href="/fields/new">
              <Button size="sm">Register a field</Button>
            </Link>
          }
        />
      )}

      {entries && entries.length > 0 && (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Registered Fields" value={String(registeredFields)} />
            <StatCard label="Total Area" value={`${formatNumber(totalArea, "ha")} ha`} />
            <StatCard label="Rice AWD Credits" value={`${formatNumber(riceCredits, "tco2e")} tCO2e`} tone="success" />
            <StatCard label="Cropland ALM Credits" value={`${formatNumber(almCredits, "tco2e")} tCO2e`} tone="success" />
          </div>

          <div className="surface-card rounded-xl p-4">
            <PortfolioBarChart entries={entries} />
            {entries.every((e) => e.final_issuance === null) && (
              <p className="py-8 text-center text-sm text-text-tertiary">
                No field has a calculated result yet.
              </p>
            )}
          </div>

          <div className="surface-card overflow-x-auto rounded-xl">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-medium uppercase tracking-wide text-text-tertiary">
                  <th className="px-4 pb-2.5 pt-4">Field</th>
                  <th className="px-4 pb-2.5 pt-4">District</th>
                  <th className="px-4 pb-2.5 pt-4">Type</th>
                  <th className="px-4 pb-2.5 pt-4 text-right">Area (ha)</th>
                  <th className="px-4 pb-2.5 pt-4 text-right">Latest Credits (tCO2e)</th>
                  <th className="px-4 pb-2.5 pt-4">Last Calculated</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e.field_id} className="border-t border-border/60">
                    <td className="px-4 py-3">
                      <Link href={`/fields/${e.field_id}/ledger`} className="flex items-center gap-2 text-text-primary hover:underline">
                        <IconTile icon={LayoutGrid} size="sm" />
                        {e.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{e.district}</td>
                    <td className="px-4 py-3 text-text-secondary">{FIELD_TYPE_LABELS[e.field_type] ?? e.field_type}</td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums">{formatNumber(e.area_ha, "ha")}</td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums">
                      {e.final_issuance !== null ? formatNumber(e.final_issuance, "tco2e") : "Not calculated"}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">{e.calculated_at ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
