"use client";

import { useState } from "react";
import { useSession } from "@/app/providers";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Select, TextInput } from "@/components/ui/Field";
import {
  useCreateCustodyEvent, useCreateLabResult, useCreatePlan, useCreateSample, useCreateSocEvidenceReview,
  useCreateStratum, useCustodyEvents, useLabResults, useSocEvidence, useSoilPlans, useSoilSamples, useSoilStrata,
} from "@/hooks/use-soil-evidence";
import { ApiError } from "@/lib/api";

const SITE_TYPES = ["project", "control"] as const;
const TIMEPOINTS = ["t_start", "t_final"] as const;

function SampleRow({ fieldId, planId, sample }: { fieldId: string; planId: string; sample: { sample_id: string; site_type: string; timepoint: string; sample_date: string; depth_top_cm: number; depth_bottom_cm: number; soc_value_tco2e_ha: number | null; lab_name: string; chain_of_custody_ref: string } }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const labResults = useLabResults(fieldId, open ? sample.sample_id : "");
  const custodyEvents = useCustodyEvents(fieldId, open ? sample.sample_id : "");
  const createLabResult = useCreateLabResult(fieldId, sample.sample_id);
  const createCustodyEvent = useCreateCustodyEvent(fieldId, sample.sample_id);

  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm"
      >
        <span className="flex items-center gap-2">
          <Badge tone="neutral">{sample.site_type}</Badge>
          <Badge tone="neutral">{sample.timepoint}</Badge>
          <span className="text-text-secondary">{sample.sample_date}</span>
          <span className="font-mono text-xs text-text-tertiary">{sample.depth_top_cm}-{sample.depth_bottom_cm}cm</span>
        </span>
        <span className="font-mono tabular-nums">{sample.soc_value_tco2e_ha ?? "—"} tCO2e/ha</span>
      </button>
      {open && (
        <div className="space-y-4 border-t border-border p-3">
          {error && <p role="alert" className="rounded bg-danger-50 p-2 text-xs text-danger-700">{error}</p>}
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">Lab results</h4>
            <ul className="mb-2 space-y-1 text-sm">
              {labResults.data?.map((r) => (
                <li key={r.result_id} className="flex justify-between font-mono text-xs">
                  <span>{r.analyte} · {r.method}</span>
                  <span>{r.value} {r.unit}{r.lab_name ? ` (${r.lab_name})` : ""}</span>
                </li>
              ))}
              {labResults.data?.length === 0 && <li className="text-xs text-text-tertiary">No lab results recorded yet.</li>}
            </ul>
            <form
              className="grid grid-cols-2 gap-2 sm:grid-cols-5"
              onSubmit={(e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                createLabResult.mutate(
                  {
                    analyte: data.get("analyte"), method: data.get("method"), unit: data.get("unit"),
                    value: Number(data.get("value")), lab_name: data.get("lab_name"),
                    analyzed_at: data.get("analyzed_at") || null, notes: "",
                  },
                  { onError: (err) => setError(err instanceof ApiError ? err.detail : "Failed to save"), onSuccess: () => e.currentTarget.reset() },
                );
              }}
            >
              <Select name="analyte" defaultValue="soc_percent" className="col-span-2 sm:col-span-1">
                <option value="soc_percent">SOC %</option>
                <option value="bulk_density_g_cm3">Bulk density</option>
                <option value="soc_stock_tco2e_ha">SOC stock</option>
                <option value="other">Other</option>
              </Select>
              <TextInput name="method" placeholder="Method" required />
              <TextInput name="unit" placeholder="Unit" required />
              <TextInput name="value" type="number" step="any" placeholder="Value" required />
              <TextInput name="lab_name" placeholder="Lab name" />
              <TextInput name="analyzed_at" type="date" className="col-span-2" />
              <Button type="submit" size="sm" loading={createLabResult.isPending}>Add result</Button>
            </form>
          </div>
          <div>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">Chain of custody</h4>
            <ul className="mb-2 space-y-1 text-sm">
              {custodyEvents.data?.map((ev) => (
                <li key={ev.event_id} className="flex justify-between font-mono text-xs">
                  <span>{ev.event_type} — {ev.event_at}</span>
                  <span>{ev.actor}{ev.location ? ` @ ${ev.location}` : ""}</span>
                </li>
              ))}
              {custodyEvents.data?.length === 0 && <li className="text-xs text-text-tertiary">No custody events recorded yet.</li>}
            </ul>
            <form
              className="grid grid-cols-2 gap-2 sm:grid-cols-4"
              onSubmit={(e) => {
                e.preventDefault();
                const data = new FormData(e.currentTarget);
                createCustodyEvent.mutate(
                  { event_type: data.get("event_type"), event_at: data.get("event_at"), actor: data.get("actor"), location: data.get("location"), notes: "" },
                  { onError: (err) => setError(err instanceof ApiError ? err.detail : "Failed to save"), onSuccess: () => e.currentTarget.reset() },
                );
              }}
            >
              <Select name="event_type" defaultValue="collected">
                <option value="collected">Collected</option>
                <option value="packaged">Packaged</option>
                <option value="shipped">Shipped</option>
                <option value="received_by_lab">Received by lab</option>
                <option value="analyzed">Analyzed</option>
                <option value="disposed">Disposed</option>
                <option value="other">Other</option>
              </Select>
              <TextInput name="event_at" type="date" required />
              <TextInput name="actor" placeholder="Actor" />
              <TextInput name="location" placeholder="Location" />
              <Button type="submit" size="sm" className="col-span-2 sm:col-span-4 w-fit" loading={createCustodyEvent.isPending}>Add event</Button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function SocEvidenceReviewPanel({ fieldId }: { fieldId: string }) {
  const evidence = useSocEvidence(fieldId);
  const review = useCreateSocEvidenceReview(fieldId);
  const [error, setError] = useState("");

  return (
    <Card>
      <h3 className="mb-1 font-medium text-text-primary">Reviewed SOC evidence mapping</h3>
      <p className="mb-3 text-sm text-text-secondary">
        For each cell, adopt a specific set of sample rows as the calculation input, or view why the legacy
        aggregate is still governing. Adopting requires at least 3 sample rows with a recorded SOC value.
      </p>
      {error && <p role="alert" className="mb-2 rounded bg-danger-50 p-2 text-xs text-danger-700">{error}</p>}
      <div className="grid gap-3 sm:grid-cols-2">
        {SITE_TYPES.flatMap((siteType) =>
          TIMEPOINTS.map((timepoint) => {
            const key = `${siteType}_${timepoint}`;
            const cell = evidence.data?.[key];
            if (!cell) return null;
            const sourceTone = cell.source === "reviewed_evidence" ? "success" : cell.source === "legacy_aggregate" ? "warning" : "danger";
            return (
              <div key={key} className="rounded-lg border border-border p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium">{siteType} / {timepoint}</span>
                  <Badge tone={sourceTone}>{cell.source.replace("_", " ")}{cell.review?.stale ? " (stale)" : ""}</Badge>
                </div>
                <p className="mb-2 font-mono text-xs text-text-tertiary">{cell.values.length} value(s): {cell.values.join(", ") || "none"}</p>
                {cell.note && <p className="mb-2 text-xs text-text-tertiary">{cell.note}</p>}
                <p className="mb-2 text-xs text-text-secondary">{cell.eligible_sample_ids.length} eligible sample(s) recorded for this cell.</p>
                <form
                  className="space-y-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const data = new FormData(e.currentTarget);
                    const selectedIds = data.getAll("sample_id").map(String);
                    review.mutate(
                      { site_type: siteType, timepoint, sample_ids: selectedIds, status: String(data.get("status")), reason: String(data.get("reason")) },
                      { onError: (err) => setError(err instanceof ApiError ? err.detail : "Failed to save review") },
                    );
                  }}
                >
                  <div className="max-h-28 space-y-1 overflow-y-auto rounded border border-border p-2">
                    {cell.eligible_sample_ids.length === 0 && <p className="text-xs text-text-tertiary">No samples with a SOC value recorded yet.</p>}
                    {cell.eligible_sample_ids.map((sid) => (
                      <label key={sid} className="flex items-center gap-2 font-mono text-xs">
                        <input type="checkbox" name="sample_id" value={sid} defaultChecked={cell.review?.sample_ids.includes(sid)} />
                        {sid.slice(0, 8)}
                      </label>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <Select name="status" defaultValue="adopted" className="w-32">
                      <option value="adopted">Adopt</option>
                      <option value="rejected">Reject</option>
                    </Select>
                    <TextInput name="reason" placeholder="Reason (required)" required className="flex-1" />
                  </div>
                  <Button type="submit" size="sm" loading={review.isPending}>Save decision</Button>
                </form>
              </div>
            );
          }),
        )}
      </div>
    </Card>
  );
}

export default function SoilEvidencePage() {
  const field = useFieldContext();
  const session = useSession();
  const writable = session?.role === "admin" || session?.role === "analyst";
  const fieldId = field.field_id;
  const [selectedPlan, setSelectedPlan] = useState("");
  const [error, setError] = useState("");

  const plans = useSoilPlans(fieldId);
  const planId = selectedPlan || plans.data?.[0]?.plan_id || "";
  const strata = useSoilStrata(fieldId, planId);
  const samples = useSoilSamples(fieldId, planId);
  const createPlan = useCreatePlan(fieldId);
  const createStratum = useCreateStratum(fieldId, planId);
  const createSample = useCreateSample(fieldId, planId);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-semibold">Soil evidence</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Sampling plans, strata, geolocated samples, per-analyte lab results, and chain of custody. Adopting a
          reviewed sample set below is what actually feeds the SOC calculation — recording samples alone does not.
        </p>
      </div>
      {error && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{error}</p>}

      {writable && (
        <Card>
          <h3 className="mb-3 font-medium">New sampling plan</h3>
          <form
            className="grid gap-3 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              const data = new FormData(e.currentTarget);
              createPlan.mutate(
                {
                  name: String(data.get("name")), description: String(data.get("description") ?? ""),
                  measurement_method: String(data.get("measurement_method")),
                  remeasurement_interval_years: data.get("remeasurement_interval_years") ? Number(data.get("remeasurement_interval_years")) : null,
                },
                { onError: (err) => setError(err instanceof ApiError ? err.detail : "Failed to save"), onSuccess: () => e.currentTarget.reset() },
              );
            }}
          >
            <div>
              <FieldLabel>Name</FieldLabel>
              <TextInput name="name" required />
            </div>
            <div>
              <FieldLabel>Measurement method</FieldLabel>
              <Select name="measurement_method" defaultValue="dry_combustion">
                <option value="dry_combustion">Dry combustion</option>
                <option value="wet_oxidation">Wet oxidation</option>
                <option value="loss_on_ignition">Loss on ignition</option>
                <option value="other">Other</option>
              </Select>
            </div>
            <div>
              <FieldLabel>Description</FieldLabel>
              <TextInput name="description" />
            </div>
            <div>
              <FieldLabel>Remeasurement interval (years)</FieldLabel>
              <TextInput name="remeasurement_interval_years" type="number" step="any" />
            </div>
            <Button type="submit" className="w-fit" loading={createPlan.isPending}>Create plan</Button>
          </form>
        </Card>
      )}

      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-medium">Sampling plans</h3>
          {plans.data && plans.data.length > 0 && (
            <Select value={planId} onChange={(e) => setSelectedPlan(e.target.value)} className="w-64">
              {plans.data.map((p) => (
                <option key={p.plan_id} value={p.plan_id}>{p.name} ({p.measurement_method})</option>
              ))}
            </Select>
          )}
        </div>
        {plans.data?.length === 0 && <p className="text-sm text-text-tertiary">No sampling plans yet.</p>}
      </Card>

      {planId && (
        <>
          {writable && (
            <Card>
              <h3 className="mb-3 font-medium">New stratum</h3>
              <form
                className="flex flex-wrap gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = new FormData(e.currentTarget);
                  createStratum.mutate(
                    { name: String(data.get("name")), description: "", area_ha: data.get("area_ha") ? Number(data.get("area_ha")) : null },
                    { onError: (err) => setError(err instanceof ApiError ? err.detail : "Failed to save"), onSuccess: () => e.currentTarget.reset() },
                  );
                }}
              >
                <TextInput name="name" placeholder="Stratum name" required />
                <TextInput name="area_ha" type="number" step="any" placeholder="Area (ha)" />
                <Button type="submit" loading={createStratum.isPending}>Add stratum</Button>
              </form>
              <ul className="mt-3 flex flex-wrap gap-2 text-xs">
                {strata.data?.map((s) => <li key={s.stratum_id}><Badge tone="neutral">{s.name}{s.area_ha ? ` (${s.area_ha}ha)` : ""}</Badge></li>)}
              </ul>
            </Card>
          )}

          {writable && (
            <Card>
              <h3 className="mb-3 font-medium">New sample</h3>
              <form
                className="grid gap-2 sm:grid-cols-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  const data = new FormData(e.currentTarget);
                  createSample.mutate(
                    {
                      stratum_id: data.get("stratum_id") || null,
                      site_type: data.get("site_type"), timepoint: data.get("timepoint"),
                      sample_date: data.get("sample_date"),
                      latitude: data.get("latitude") ? Number(data.get("latitude")) : null,
                      longitude: data.get("longitude") ? Number(data.get("longitude")) : null,
                      depth_top_cm: Number(data.get("depth_top_cm")), depth_bottom_cm: Number(data.get("depth_bottom_cm")),
                      bulk_density_g_cm3: data.get("bulk_density_g_cm3") ? Number(data.get("bulk_density_g_cm3")) : null,
                      soc_percent: data.get("soc_percent") ? Number(data.get("soc_percent")) : null,
                      soc_value_tco2e_ha: data.get("soc_value_tco2e_ha") ? Number(data.get("soc_value_tco2e_ha")) : null,
                      lab_name: data.get("lab_name") || "", lab_method: data.get("lab_method") || "",
                      chain_of_custody_ref: data.get("chain_of_custody_ref") || "", notes: "",
                    },
                    { onError: (err) => setError(err instanceof ApiError ? err.detail : "Failed to save"), onSuccess: () => e.currentTarget.reset() },
                  );
                }}
              >
                <Select name="site_type" defaultValue="project"><option value="project">Project</option><option value="control">Control</option></Select>
                <Select name="timepoint" defaultValue="t_start"><option value="t_start">t_start</option><option value="t_final">t_final</option></Select>
                <Select name="stratum_id" defaultValue="">
                  <option value="">No stratum</option>
                  {strata.data?.map((s) => <option key={s.stratum_id} value={s.stratum_id}>{s.name}</option>)}
                </Select>
                <TextInput name="sample_date" type="date" required />
                <TextInput name="depth_top_cm" type="number" step="any" placeholder="Depth top (cm)" required />
                <TextInput name="depth_bottom_cm" type="number" step="any" placeholder="Depth bottom (cm)" required />
                <TextInput name="latitude" type="number" step="any" placeholder="Latitude" />
                <TextInput name="longitude" type="number" step="any" placeholder="Longitude" />
                <TextInput name="bulk_density_g_cm3" type="number" step="any" placeholder="Bulk density g/cm3" />
                <TextInput name="soc_percent" type="number" step="any" placeholder="SOC %" />
                <TextInput name="soc_value_tco2e_ha" type="number" step="any" placeholder="SOC value tCO2e/ha" />
                <TextInput name="lab_name" placeholder="Lab name" />
                <TextInput name="lab_method" placeholder="Lab method" />
                <TextInput name="chain_of_custody_ref" placeholder="Custody ref (summary)" />
                <Button type="submit" className="w-fit" loading={createSample.isPending}>Add sample</Button>
              </form>
            </Card>
          )}

          <Card>
            <h3 className="mb-3 font-medium">Samples</h3>
            <div className="space-y-2">
              {samples.data?.map((s) => <SampleRow key={s.sample_id} fieldId={fieldId} planId={planId} sample={s} />)}
              {samples.data?.length === 0 && <p className="text-sm text-text-tertiary">No samples recorded yet for this plan.</p>}
            </div>
          </Card>
        </>
      )}

      <SocEvidenceReviewPanel fieldId={fieldId} />
    </div>
  );
}
