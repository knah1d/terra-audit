"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Sparkles } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { DerivationTrail, type DerivationStep } from "@/components/ledger/DerivationTrail";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { StatCard } from "@/components/ui/Card";
import { ErrorText, FieldLabel, Select, TextInput } from "@/components/ui/Field";
import { RoleGate } from "@/components/ui/RoleGate";
import { useCommitCarbonCredits, usePreviewCarbonCredits } from "@/hooks/use-carbon";
import { formatNumber } from "@/lib/format";
import { AMENDMENT_TYPE_OPTIONS, ledgerRiceSchema, type LedgerRiceForm as FormValues } from "@/lib/schemas/ledger";
import type { CarbonResult } from "@/types/api";

// zod v4's z.coerce.number() makes the schema's *input* type (string |
// unknown, pre-coercion) diverge from its *output* type (number,
// post-coercion) — react-hook-form's 3-generic useForm<TFieldValues,
// TContext, TTransformedValues> exists specifically to model this: form
// inputs/register() see the raw (pre-coerce) shape, while
// handleSubmit()'s callback receives the validated/coerced FormValues.
type RiceFormInput = z.input<typeof ledgerRiceSchema>;

function buildSteps(cr: CarbonResult): DerivationStep[] {
  return [
    {
      id: "sf_w",
      title: "Project water-regime scaling factor (SF_w)",
      description: "VM0051 §8.2.3 Eq. 6/7, Table 5.12 — scales baseline continuous-flooding CH₄ down based on verified AWD drydown events.",
      formula: "SF_{w,project} \\in \\{1.00,\\ 0.71,\\ 0.55\\}",
      substitution: `SF_{w,project} = ${formatNumber(cr.sf_w_project as number)}`,
      result: { label: "SF_w", value: cr.sf_w_project as number, unit: "" },
    },
    {
      id: "e_baseline",
      title: "Baseline scenario CH₄ emissions",
      formula: "E_{bsl} = EF_c \\times SF_{w,bsl} \\times SC_p \\times SC_o \\times \\text{days} \\times \\text{area}",
      substitution: `E_{bsl} = ${formatNumber(cr.ef_c_used as number)} \\times 1.00 \\times ${formatNumber(cr.sc_preseason as number)} \\times ${formatNumber(cr.sc_organic_bsl as number)} \\times \\text{days} \\times \\text{ha}`,
      result: { label: "E_baseline", value: cr.e_baseline as number, unit: "tCO2e" },
    },
    {
      id: "e_project",
      title: "Project scenario CH₄ emissions",
      formula: "E_{wp} = EF_c \\times SF_{w,project} \\times SC_p \\times SC_o \\times \\text{days} \\times \\text{area}",
      result: { label: "E_project", value: cr.e_project as number, unit: "tCO2e" },
    },
    {
      id: "delta_e",
      title: "Gross CH₄ reduction",
      formula: "\\Delta E_{CH_4} = E_{bsl} - E_{wp}",
      result: { label: "ΔE_CH4", value: cr.delta_e_co2e as number, unit: "tCO2e" },
    },
    {
      id: "uncertainty",
      title: "QA3 flat uncertainty deduction (§8.6.3)",
      formula: "UNC = \\Delta E_{CH_4} \\times 0.15",
      substitution: `UNC = ${formatNumber(cr.delta_e_co2e as number)} \\times ${formatNumber((cr.unc_deduction_pct as number) / 100)}`,
      result: { label: "After uncertainty", value: cr.ch4_after_unc as number, unit: "tCO2e" },
    },
    {
      id: "n2o",
      title: "N₂O project-emission penalty (§8.3.2 Eq. 25)",
      description: "Mandatory Eq. 29 project emission whenever AWD events > 0 — not §8.4 leakage.",
      formula: "PE_{N_2O} = f(Q_N)",
      result: { label: "N2O penalty", value: cr.pe_n2o_tco2e as number, unit: "tCO2e", },
      tone: (cr.pe_n2o_tco2e as number) > 0 ? "warning" : "neutral",
    },
    {
      id: "final",
      title: "Final issuance (Eq. 29)",
      formula: "\\text{Issuance} = \\max(0,\\ \\text{CH}_4\\text{ after unc.} - PE_{N_2O})",
      result: { label: "Final Issuance", value: cr.final_issuance, unit: "tCO2e" },
      tone: "success",
    },
  ];
}

export function LedgerRiceForm({
  fieldId,
  defaultArea,
}: {
  fieldId: string;
  defaultArea: number;
}) {
  const [result, setResult] = useState<CarbonResult | null>(null);
  const [committed, setCommitted] = useState(false);
  const preview = usePreviewCarbonCredits(fieldId);
  const commit = useCommitCarbonCredits(fieldId);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RiceFormInput, unknown, FormValues>({
    resolver: zodResolver(ledgerRiceSchema),
    defaultValues: {
      season_length_days: 120,
      area_ha: defaultArea,
      awd_events: 0,
      q_n_kg_per_ha: 100,
      preseason_category: "short",
      baseline_amendment_type: "straw_shortly_before",
      baseline_amendment_rate: 5,
      project_amendment_type: "straw_shortly_before",
      project_amendment_rate: 5,
    },
  });

  function toRequestBody(values: FormValues) {
    return {
      season_length_days: values.season_length_days,
      area_ha: values.area_ha,
      awd_events: values.awd_events,
      q_n_kg_per_ha: values.q_n_kg_per_ha,
      preseason_category: values.preseason_category,
      baseline_amendments: [[values.baseline_amendment_type, values.baseline_amendment_rate]],
      project_amendments: [[values.project_amendment_type, values.project_amendment_rate]],
    };
  }

  async function onPreview(values: FormValues) {
    setCommitted(false);
    const body = toRequestBody(values);
    const cr = await preview.mutateAsync(body);
    setResult(cr);
  }

  async function onCommit(values: FormValues) {
    const body = toRequestBody(values);
    const cr = await preview.mutateAsync(body); // recompute against latest form values
    setResult(cr);
    if (cr.qa3_pathway_valid === false) return; // blocked — don't attempt commit
    await commit.mutateAsync({ body, idempotencyKey: crypto.randomUUID() });
    setCommitted(true);
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit(onPreview)} className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <FieldLabel>Season Length (days)</FieldLabel>
          <TextInput type="number" {...register("season_length_days")} />
          <ErrorText>{errors.season_length_days?.message}</ErrorText>
        </div>
        <div>
          <FieldLabel>Field Area (ha)</FieldLabel>
          <TextInput type="number" step="0.01" {...register("area_ha")} />
          <ErrorText>{errors.area_ha?.message}</ErrorText>
        </div>
        <div>
          <FieldLabel>AWD Events (verified)</FieldLabel>
          <TextInput type="number" {...register("awd_events")} />
          <ErrorText>{errors.awd_events?.message}</ErrorText>
        </div>
        <div>
          <FieldLabel>N Input (kg N/ha)</FieldLabel>
          <TextInput type="number" {...register("q_n_kg_per_ha")} />
          <ErrorText>{errors.q_n_kg_per_ha?.message}</ErrorText>
        </div>

        <div className="col-span-2">
          <FieldLabel>Pre-season water regime (Table 5.13)</FieldLabel>
          <Select {...register("preseason_category")}>
            <option value="short">Non-flooded pre-season &lt; 180 days (double/multi-cropping)</option>
            <option value="long">Non-flooded pre-season &gt; 180 days (single cropping)</option>
          </Select>
        </div>

        <div>
          <FieldLabel>Baseline organic amendment</FieldLabel>
          <Select {...register("baseline_amendment_type")}>
            {AMENDMENT_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </Select>
          <TextInput type="number" step="0.1" className="mt-1" {...register("baseline_amendment_rate")} placeholder="Rate (t/ha)" />
        </div>
        <div>
          <FieldLabel>Project organic amendment</FieldLabel>
          <Select {...register("project_amendment_type")}>
            {AMENDMENT_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </Select>
          <TextInput type="number" step="0.1" className="mt-1" {...register("project_amendment_rate")} placeholder="Rate (t/ha)" />
        </div>

        <div className="col-span-full flex gap-3">
          <Button type="submit" variant="secondary" loading={preview.isPending}>
            Calculate (preview)
          </Button>
          <RoleGate allow={["admin", "analyst"]}>
            <Button
              type="button"
              icon={Sparkles}
              onClick={handleSubmit(onCommit)}
              loading={commit.isPending}
              disabled={preview.isPending}
            >
              Calculate &amp; Save Carbon Credits
            </Button>
          </RoleGate>
        </div>
      </form>

      {result && result.qa3_pathway_valid === false && (
        <Alert tone="danger" title="Issuance blocked">
          {result.qa3_block_reason as string}
        </Alert>
      )}

      {result && result.qa3_pathway_valid !== false && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Final Issuance" value={`${formatNumber(result.final_issuance, "tco2e")} tCO2e`} tone="success" />
            <StatCard label="Gross ΔCH4" value={`${formatNumber(result.delta_e_co2e as number, "tco2e")} tCO2e`} />
            <StatCard label="N2O Penalty" value={`${formatNumber(result.pe_n2o_tco2e as number, "tco2e")} tCO2e`} />
            <StatCard label="Uncertainty Deduction" value={`${formatNumber(result.unc_deduction_pct as number, "%")}%`} />
          </div>
          <DerivationTrail steps={buildSteps(result)} />
          {committed && <Alert tone="success">Saved to credit history.</Alert>}
        </>
      )}
    </div>
  );
}
