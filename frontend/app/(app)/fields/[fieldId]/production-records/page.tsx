"use client";
import { formatDate, formatQueueTimestamp, formatNumber } from "@/lib/format";

import { ExplainButton } from "@/components/ai/ExplainDrawer";

import { useState } from "react";
import { useSession } from "@/app/providers";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextArea, TextInput } from "@/components/ui/Field";
import { useCreateProductionRecord, useImportProductionRecords, useProductionRecords, useLeakageAssessments, useSaveLeakageAssessment } from "@/hooks/use-production-records";
import { useProjects } from "@/hooks/use-projects";
import { useProjectApplicability } from "@/hooks/use-methodology";
import type { LeakageAssessment } from "@/hooks/use-production-records";
import { ApiError } from "@/lib/api";
import type { ProductionRecordOut } from "@/types/api";

function RecordsTable({ records }: { records: ProductionRecordOut[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="text-text-tertiary">
            <th className="pr-3 py-1">Commodity</th>
            <th className="pr-3 py-1">Period</th>
            <th className="pr-3 py-1">Label</th>
            <th className="pr-3 py-1">Cycle</th>
            <th className="pr-3 py-1">Area share</th>
            <th className="pr-3 py-1">Status</th>
            <th className="pr-3 py-1">Quantity</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.record_id} className="border-t border-border font-mono">
              <td className="pr-3 py-1">{r.commodity}</td>
              <td className="pr-3 py-1">{r.period_type}</td>
              <td className="pr-3 py-1">{r.period_label}</td>
              <td className="pr-3 py-1">{r.crop_cycle_index}</td>
              <td className="pr-3 py-1">{formatNumber(r.area_share_pct, "%")}%</td>
              <td className="pr-3 py-1"><Badge tone={r.production_status === "produced" ? "success" : r.production_status === "missing" ? "danger" : "neutral"}>{r.production_status}</Badge></td>
              <td className="pr-3 py-1">{formatNumber(r.production_quantity)} {r.unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {records.length === 0 && <p className="mt-2 text-sm text-text-tertiary">No production records yet.</p>}
    </div>
  );
}

function LeakageCalculator({ fieldId, commodities, writable }: { fieldId: string; commodities: string[]; writable: boolean }) {
  const saved = useLeakageAssessments(fieldId);
  const [selected, setSelected] = useState("");
  const initial = saved.data?.find((a) => a.assessment_id === selected);
  return <Card>
    <h3 className="ui-subsection-title">Saved leakage assessments</h3>
    {saved.error && <p role="alert">Unable to load saved assessments.</p>}
    <Select value={selected} onChange={(e) => setSelected(e.target.value)}>
      <option value="">New assessment</option>
      {saved.data?.map((a) => <option key={a.assessment_id} value={a.assessment_id}>{formatDate(a.period_start)} – {formatDate(a.period_end)} · {a.project_id} · {formatQueueTimestamp(a.created_at)}</option>)}
    </Select>
    {initial && <ExplainButton projectId={initial.project_id} request={{ action: "explain_leakage", field_id: fieldId, assessment_id: initial.assessment_id }}>Explain this leakage result</ExplainButton>}
    {initial && <details className="my-2 text-sm"><summary>Stored evidence and parameters</summary><pre className="overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(initial.payload, null, 2)}</pre></details>}
    {writable && <LeakageAssessmentForm key={selected || "new"} fieldId={fieldId} commodities={commodities} initial={initial} />}
  </Card>;
}

function LeakageAssessmentForm({ fieldId, commodities, initial }: { fieldId: string; commodities: string[]; initial?: LeakageAssessment }) {
  const save = useSaveLeakageAssessment(fieldId);
  const projects = useProjects();
  const p = initial?.payload ?? {};
  const [projectId, setProjectId] = useState(String(p.project_id ?? ""));
  const applicability = useProjectApplicability(projectId, projectId ? "vm0042_alm" : undefined);
  const [error, setError] = useState("");
  const params = (p.commodity_params ?? {}) as Record<string, Record<string, unknown>>;
  const region = (p.new_land_carbon_stock_params ?? {}) as Record<string, unknown>;
  const defaultText = (key: string) => Array.isArray(p[key]) ? (p[key] as string[]).join(", ") : String(p[key] ?? "");
  const result = save.data?.result;
  return <form className="mt-4 space-y-4" onSubmit={(e) => {
    e.preventDefault(); setError("");
    const d = new FormData(e.currentTarget);
    const number = (key: string) => d.get(key) === "" ? null : Number(d.get(key));
    const text = (key: string) => String(d.get(key) ?? "").trim();
    const commodityParams: Record<string, unknown> = {};
    for (const c of commodities) commodityParams[c] = {
      commodity_type: text(`type_${c}`), unit: text(`unit_${c}`),
      growth_rate_pct: number(`growth_${c}`), growth_rate_source: text(`growth_source_${c}`) || null,
      yield_units_per_ha: number(`yield_${c}`), yield_source: text(`yield_source_${c}`) || null,
      cross_commodity_evidence: text(`cross_${c}`),
      is_override_pct: number(`is_${c}`), nl_override_pct: number(`nl_${c}`),
      override_justification: text(`override_${c}`) || null,
    };
    const regionalKeys = ["delta_cbiomass_t_c_ha", "soc_ref_t_c_ha", "f_lu", "f_mg", "f_in"];
    const hasRegional = regionalKeys.some((key) => text(key) !== "") || !!text("factors_source");
    const body: Record<string, unknown> = {
      project_id: projectId, bundle_id: applicability.data?.resolved_bundle?.bundle_id,
      module_version: "1.1", accounting_mode: text("accounting_mode"), years_elapsed: number("years_elapsed"),
      commodity_params: commodityParams,
      new_land_carbon_stock_params: hasRegional ? { ...Object.fromEntries(regionalKeys.map((key) => [key, number(key)])), factors_source: text("factors_source") } : null,
      historical_period_labels: text("historical_period_labels").split(",").map((v) => v.trim()).filter(Boolean),
      project_period_labels: text("project_period_labels").split(",").map((v) => v.trim()).filter(Boolean),
      prior_cumulative_leakage_tco2e: number("prior_cumulative_leakage_tco2e"),
      prior_verification_end: text("prior_verification_end") || null,
      prior_verification_reference: text("prior_verification_reference"),
    };
    for (const key of ["monitoring_period_start", "monitoring_period_end", "project_start", "historical_start", "historical_end", "mitigation_choice", "mitigation_reason", "scope_evidence", "regional_land_cover_evidence"]) body[key] = text(key);
    save.mutate(body, { onError: (err) => setError(err instanceof ApiError ? err.detail : "Unable to save assessment") });
  }}>
    {error && <p role="alert" className="text-sm text-danger-700">{error}</p>}
    <div className="grid gap-3 sm:grid-cols-2">
      <label>Project<Select required value={projectId} onChange={(e) => setProjectId(e.target.value)}><option value="">Select project</option>{projects.data?.map((project) => <option key={project.project_id} value={project.project_id}>{project.name}</option>)}</Select></label>
      <p className="text-sm">Methodology: {applicability.data?.resolved_bundle?.bundle_version ?? "Select a project with an applicable bundle"}</p>
      {[["project_start", "Project start"], ["historical_start", "History start"], ["historical_end", "History end (inclusive)"], ["monitoring_period_start", "Monitoring start"], ["monitoring_period_end", "Monitoring end (inclusive)"]].map(([key, label]) => <label key={key}>{label}<TextInput name={key} type="date" defaultValue={defaultText(key)} required /></label>)}
      <label>Years since project start<TextInput name="years_elapsed" type="number" min={1} step={1} defaultValue={defaultText("years_elapsed") || "1"} required /></label>
      <label>Historical annual labels, oldest first<TextInput name="historical_period_labels" defaultValue={defaultText("historical_period_labels")} placeholder="2021, 2022, 2023" required /></label>
      <label>Monitoring annual labels, oldest first<TextInput name="project_period_labels" defaultValue={defaultText("project_period_labels")} placeholder="2024" required /></label>
      <label>Accounting mode<Select name="accounting_mode" defaultValue={defaultText("accounting_mode") || "leakage_only"}><option value="leakage_only">Leakage only</option><option value="cross_commodity">Cross-commodity production</option></Select></label>
      <label>Step 2 mitigation<Select name="mitigation_choice" defaultValue={defaultText("mitigation_choice")} required><option value="">Select explicitly</option><option value="none">No mitigation activity or claim</option><option value="claimed">Mitigation claimed (currently unsupported)</option></Select></label>
    </div>
    <label className="block">Step 2 declaration and reason<TextArea name="mitigation_reason" defaultValue={defaultText("mitigation_reason")} required /></label>
    <label className="block">Scope and completeness evidence<TextArea name="scope_evidence" defaultValue={defaultText("scope_evidence")} placeholder="Complete historical rotation, affected commodities, non-overlapping field scope and consistent project-wide accounting choices" required /></label>
    <h4 className="font-medium">Commodity parameters</h4>
    {commodities.map((c) => {
      const v = params[c] ?? {};
      return <fieldset key={c} className="grid gap-2 rounded border border-border p-3 sm:grid-cols-2"><legend>{c}</legend>
        <label>Type<Select name={`type_${c}`} defaultValue={String(v.commodity_type ?? "agricultural")}><option value="agricultural">Agricultural</option><option value="fuelwood">Fuelwood</option></Select></label>
        <label>Production / yield numerator unit<TextInput name={`unit_${c}`} defaultValue={String(v.unit ?? "")} placeholder="t, kg, etc.; must match records" required /></label>
        <label>Yield per hectare per year<TextInput name={`yield_${c}`} type="number" step="any" defaultValue={String(v.yield_units_per_ha ?? "")} /></label>
        <label>Yield source<TextInput name={`yield_source_${c}`} defaultValue={String(v.yield_source ?? "")} /></label>
        <label>Growth rate % (blank = 2.5 default)<TextInput name={`growth_${c}`} type="number" step="any" defaultValue={String(v.growth_rate_pct ?? "")} /></label>
        <label>Custom growth-rate source<TextInput name={`growth_source_${c}`} defaultValue={String(v.growth_rate_source ?? "")} /></label>
        <label>Increased supply override %<TextInput name={`is_${c}`} type="number" step="any" defaultValue={String(v.is_override_pct ?? "")} /></label>
        <label>New land override %<TextInput name={`nl_${c}`} type="number" step="any" defaultValue={String(v.nl_override_pct ?? "")} /></label>
        <label>Override evidence<TextInput name={`override_${c}`} defaultValue={String(v.override_justification ?? "")} /></label>
        <label>Cross-commodity national production / increasing-production evidence<TextInput name={`cross_${c}`} defaultValue={String(v.cross_commodity_evidence ?? "")} /></label>
      </fieldset>;
    })}
    <h4 className="font-medium">Regional parameters (required when net land impact is positive)</h4>
    <div className="grid gap-3 sm:grid-cols-2">
      {[["delta_cbiomass_t_c_ha", "Biomass carbon loss (t C/ha)"], ["soc_ref_t_c_ha", "Reference SOC (t C/ha)"], ["f_lu", "Land-use factor"], ["f_mg", "Management factor"], ["f_in", "Input factor"]].map(([key, label]) => <label key={key}>{label}<TextInput name={key} type="number" step="any" defaultValue={String(region[key] ?? "")} /></label>)}
      <label>Factor sources<TextInput name="factors_source" defaultValue={String(region.factors_source ?? "")} /></label>
    </div>
    <label className="block">Regional land-cover and carbon-pool evidence<TextArea name="regional_land_cover_evidence" defaultValue={defaultText("regional_land_cover_evidence")} placeholder="Forest conversion assumption, significant pools, or documented §5.4 exception with supporting sources" /></label>
    <h4 className="font-medium">Prior external verification (required after the first period)</h4>
    <div className="grid gap-3 sm:grid-cols-3">
      <label>Cumulative leakage (tCO2e)<TextInput name="prior_cumulative_leakage_tco2e" type="number" min={0} step="any" defaultValue={defaultText("prior_cumulative_leakage_tco2e")} /></label>
      <label>Prior verification end<TextInput name="prior_verification_end" type="date" defaultValue={defaultText("prior_verification_end")} /></label>
      <label>Verified source / report reference<TextInput name="prior_verification_reference" defaultValue={defaultText("prior_verification_reference")} /></label>
    </div>
    <Button type="submit" loading={save.isPending} disabled={!applicability.data?.resolved_bundle || commodities.length === 0}>Save revision and calculate</Button>
    {result && <div className="rounded border border-border p-3 text-sm" aria-live="polite">
      <p>Revision saved. Evidence review is still required in Calculations.</p>
      <p>Cumulative leakage: {result.leakage_emissions_tco2e ?? "blocked"} tCO2e</p>
      <p>Annual displacement deduction: {result.annual_displacement_leakage_tco2e ?? "blocked"} tCO2e/year</p>
      {result.leakage_block_reason && <p className="text-warning-700">{result.leakage_block_reason}</p>}
      <details><summary>Steps and source references</summary><pre className="overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(result, null, 2)}</pre></details>
    </div>}
  </form>;
}

export default function ProductionRecordsPage() {
  const field = useFieldContext();
  const session = useSession();
  const writable = session?.role === "admin" || session?.role === "analyst";
  const fieldId = field.field_id;
  const [error, setError] = useState("");
  const [importText, setImportText] = useState("");

  const records = useProductionRecords(fieldId);
  const createRecord = useCreateProductionRecord(fieldId);
  const importRecords = useImportProductionRecords(fieldId);
  const commodities = Array.from(new Set((records.data ?? []).map((r) => r.commodity)));

  return (
    <div className="ui-container-wide space-y-6">
      <div>
        <h2 className="ui-section-title">Production records</h2>
      </div>
      {error && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{error}</p>}

      {writable && (
        <Card>
          <h3 className="ui-subsection-title mb-3">New production record</h3>
          <form
            className="grid gap-2 sm:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const data = new FormData(form);
              const status = String(data.get("production_status"));
              createRecord.mutate(
                {
                  commodity: data.get("commodity"), period_type: data.get("period_type"),
                  period_label: data.get("period_label"), crop_cycle_index: Number(data.get("crop_cycle_index") || 0),
                  harvest_start_date: data.get("harvest_start_date") || null,
                  harvest_end_date: data.get("harvest_end_date") || null,
                  harvested_area_ha: data.get("harvested_area_ha") ? Number(data.get("harvested_area_ha")) : null,
                  area_share_pct: Number(data.get("area_share_pct") || 100),
                  production_status: status,
                  production_quantity: status === "produced" ? Number(data.get("production_quantity") || 0) : null,
                  unit: status === "produced" ? data.get("unit") : "",
                  evidence_ref: data.get("evidence_ref") || "", notes: "",
                },
                { onError: (err) => setError(err instanceof ApiError ? err.detail : "Failed to save"), onSuccess: () => form.reset() },
              );
            }}
          >
            <TextInput name="commodity" placeholder="Commodity" required />
            <Select name="period_type" defaultValue="historical_year">
              <option value="historical_year">Historical year</option>
              <option value="project_period">Project period</option>
            </Select>
            <TextInput name="period_label" placeholder="Period label (e.g. 2023)" required />
            <TextInput name="crop_cycle_index" type="number" placeholder="Cycle index (0)" />
            <TextInput name="harvest_start_date" type="date" />
            <TextInput name="harvest_end_date" type="date" />
            <TextInput name="harvested_area_ha" type="number" step="any" placeholder="Harvested area (ha)" />
            <TextInput name="area_share_pct" type="number" step="any" placeholder="Area share % (100)" />
            <Select name="production_status" defaultValue="produced">
              <option value="produced">Produced</option>
              <option value="zero_production">Zero production</option>
              <option value="missing">Missing</option>
              <option value="not_applicable">Not applicable</option>
            </Select>
            <TextInput name="production_quantity" type="number" step="any" placeholder="Quantity (if produced)" />
            <TextInput name="unit" placeholder="Unit" />
            <TextInput name="evidence_ref" placeholder="Evidence reference" />
            <Button type="submit" className="w-fit" loading={createRecord.isPending}>Add record</Button>
          </form>
        </Card>
      )}

      {writable && (
        <Card>
          <h3 className="ui-subsection-title mb-2">Bulk import</h3>
          <p className="ui-meta mb-2">Paste a JSON array of records.</p>
          <TextArea value={importText} onChange={(e) => setImportText(e.target.value)} rows={4} placeholder='[{"commodity": "maize", "period_type": "historical_year", "period_label": "2022", "production_status": "produced", "production_quantity": 5, "unit": "t"}]' />
          <Button
            className="mt-2"
            loading={importRecords.isPending}
            onClick={() => {
              try {
                const parsed = JSON.parse(importText);
                importRecords.mutate(parsed, { onError: (err) => setError(err instanceof ApiError ? err.detail : "Import failed"), onSuccess: () => setImportText("") });
              } catch {
                setError("Invalid JSON");
              }
            }}
          >
            Import
          </Button>
        </Card>
      )}

      <Card>
        <h3 className="ui-subsection-title mb-3">Records</h3>
        <RecordsTable records={records.data ?? []} />
      </Card>

      <LeakageCalculator fieldId={fieldId} commodities={commodities} writable={writable} />
    </div>
  );
}
