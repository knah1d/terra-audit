"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Sparkles } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { DerivationTrail, type DerivationStep } from "@/components/ledger/DerivationTrail";
import { ExportButtons } from "@/components/ledger/ExportButtons";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { StatCard } from "@/components/ui/Card";
import { FinalIssuanceStat } from "@/components/ledger/FinalIssuanceStat";
import { ErrorText, FieldLabel, TextInput } from "@/components/ui/Field";
import { RoleGate } from "@/components/ui/RoleGate";
import { useToast } from "@/components/ui/Toast";
import { useCommitCarbonCredits, useCreditHistory, usePreviewCarbonCredits } from "@/hooks/use-carbon";
import { formatNumber } from "@/lib/format";
import { ledgerAlmSchema, type LedgerAlmForm as FormValues } from "@/lib/schemas/ledger";
import type { CarbonResult } from "@/types/api";

// See LedgerRiceForm.tsx for why this 3-generic useForm pattern is needed
// (zod v4's z.coerce.number() input/output type divergence).
type AlmFormInput = z.input<typeof ledgerAlmSchema>;

function buildSteps(cr: CarbonResult): DerivationStep[] {
  return [
    {
      id: "n2o_fert",
      title: "N₂O from fertilizer (direct + indirect, §8.2.9/8.3)",
      formula: "\\Delta N_2O_{fert} = N_2O_{fert,bsl} - N_2O_{fert,wp}",
      substitution: `${formatNumber(cr.n2o_fert_bsl as number)} - ${formatNumber(cr.n2o_fert_wp as number)}`,
      result: { label: "ΔN2O fert.", value: (cr.n2o_fert_bsl as number) - (cr.n2o_fert_wp as number), unit: "tCO2e" },
    },
    {
      id: "biomass_burning",
      title: "Biomass burning CH₄/N₂O",
      description: "IPCC 2019 Refinement Vol 4 Ch 2 Table 2.6, combustion factor keyed by crop type.",
      result: { label: "ΔCH4 (burning)", value: cr.delta_ch4_bb as number, unit: "tCO2e" },
    },
    {
      id: "livestock",
      title: "Integrated crop-livestock (enteric fermentation + manure, §8.2.6/8.2.7)",
      description: "Scoped to Pasture/Range/Paddock grazing, cattle/buffalo/sheep/goats.",
      result: {
        label: "ΔCH4 + ΔN2O livestock",
        value: (cr.delta_ch4_livestock as number) + (cr.delta_n2o_livestock as number),
        unit: "tCO2e",
      },
    },
    {
      id: "soc",
      title: "Soil organic carbon stock change (Quantification Approach 2)",
      description: "Direct paired lab measurements, §8.2.1 Eqs. 3-5/46-47.",
      formula: "\\Delta SOC = SOC_{wp} - SOC_{bsl}",
      result: {
        label: "ΔSOC",
        value: (cr.delta_co2_soil_wp as number) - (cr.delta_co2_soil_bsl as number),
        unit: "tCO2e",
      },
      tone: cr.soc_ready ? "neutral" : "warning",
    },
    {
      id: "leakage",
      title: "Production-decline leakage screening (VMD0054 Steps 1-2)",
      description: cr.other_leakage_gap_note as string | undefined,
      result: {
        label: "Foregone production",
        value: (cr.foregone_production_t as number) ?? 0,
        unit: "t",
      },
      tone: cr.foregone_production_t ? "warning" : "neutral",
    },
    {
      id: "final",
      title: "Net reductions/removals (§8.5)",
      result: { label: "Final Issuance", value: cr.final_issuance, unit: "tCO2e" },
      tone: "success",
    },
  ];
}

export function LedgerAlmForm({ fieldId, defaultArea }: { fieldId: string; defaultArea: number }) {
  const [result, setResult] = useState<CarbonResult | null>(null);
  const [committed, setCommitted] = useState(false);
  const preview = usePreviewCarbonCredits(fieldId);
  const commit = useCommitCarbonCredits(fieldId);
  const { data: history } = useCreditHistory(fieldId);
  const { show } = useToast();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AlmFormInput, unknown, FormValues>({
    resolver: zodResolver(ledgerAlmSchema),
    defaultValues: { area_ha: defaultArea, verification_years: 1.0, non_permanence_risk_pct: 20 },
  });

  async function onPreview(values: FormValues) {
    setCommitted(false);
    const cr = await preview.mutateAsync(values);
    setResult(cr);
  }

  async function onCommit(values: FormValues) {
    const cr = await preview.mutateAsync(values);
    setResult(cr);
    if (cr.production_decline_leakage_blocked) return;
    await commit.mutateAsync({ body: values, idempotencyKey: crypto.randomUUID() });
    setCommitted(true);
    show("Carbon credits saved to history", "success");
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit(onPreview)} className="grid grid-cols-3 gap-4">
        <div>
          <FieldLabel>Field Area (ha)</FieldLabel>
          <TextInput type="number" step="0.01" {...register("area_ha")} />
          <ErrorText>{errors.area_ha?.message}</ErrorText>
        </div>
        <div>
          <FieldLabel>Verification Years</FieldLabel>
          <TextInput type="number" step="0.5" {...register("verification_years")} />
          <ErrorText>{errors.verification_years?.message}</ErrorText>
        </div>
        <div>
          <FieldLabel>Non-Permanence Risk (%)</FieldLabel>
          <TextInput type="number" step="1" {...register("non_permanence_risk_pct")} />
          <ErrorText>{errors.non_permanence_risk_pct?.message}</ErrorText>
        </div>

        <div className="col-span-full flex gap-3">
          <Button type="submit" variant="secondary" loading={preview.isPending}>
            Calculate (preview)
          </Button>
          <RoleGate allow={["admin", "analyst"]}>
            <Button type="button" icon={Sparkles} onClick={handleSubmit(onCommit)} loading={commit.isPending} disabled={preview.isPending}>
              Calculate &amp; Save Carbon Credits
            </Button>
          </RoleGate>
        </div>
      </form>

      {preview.isError && (
        <Alert tone="danger" title="Calculation failed">
          {preview.error.message}
        </Alert>
      )}
      {commit.isError && (
        <Alert tone="danger" title="Save failed">
          {commit.error.message}
        </Alert>
      )}

      {result?.production_decline_leakage_blocked && (
        <Alert tone="danger" title="Issuance blocked">
          {result.leakage_block_reason as string}
        </Alert>
      )}

      {result && !result.production_decline_leakage_blocked && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <FinalIssuanceStat value={result.final_issuance} />
            <StatCard
              label="Cumulative SOC Δ"
              value={`${formatNumber(result.cumulative_delta_co2_wp as number, "tco2e")} tCO2e`}
            />
            <StatCard
              label="SOC Uncertainty"
              value={`${formatNumber(result.unc_co2_pct as number, "%")}%`}
            />
            <StatCard
              label="Other Leakage Screened"
              value={result.other_leakage_screened ? "Yes" : "No"}
              tone={result.other_leakage_screened ? "neutral" : "warning"}
            />
          </div>
          <DerivationTrail steps={buildSteps(result)} />
          {committed && <Alert tone="success">Saved to credit history.</Alert>}
        </>
      )}

      <ExportButtons
        fieldId={fieldId}
        fieldType="cropland_alm_vm0042"
        verificationId={history?.[0]?.credit_history_id ?? null}
      />
    </div>
  );
}
