"use client";

import { useState } from "react";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, TextInput } from "@/components/ui/Field";
import { RoleGate } from "@/components/ui/RoleGate";
import { usePracticeSchedule, useSocMeasurements } from "@/hooks/use-alm";
import { useSavePracticeSchedule, useSaveSocMeasurements } from "@/hooks/use-practice-form";
import type { PracticeScheduleEntry } from "@/types/api";

const EMPTY_PRACTICE: PracticeScheduleEntry = {
  crop_type: "", crop_rotation: false, cover_crops: false, intercropping: false,
  tillage: false, tillage_depth_cm: 0, residue_removed: false, residue_burned_kg_ha: 0,
  synthetic_n_rate_kg_ha: 0, organic_n_rate_kg_ha: 0, n_fixing_species: false,
  n_fixing_dry_matter_kg_ha: 0, fuel_use_l_ha: 0, crop_yield_t_ha: 0,
};

function PracticeScenarioForm({
  fieldId,
  scenario,
  initial,
}: {
  fieldId: string;
  scenario: "baseline" | "project";
  initial: PracticeScheduleEntry | null;
}) {
  // `initial` is already resolved (loading is gated by the caller), so a lazy
  // initializer captures it once at mount — no effect-based resync needed.
  const [values, setValues] = useState<PracticeScheduleEntry>(() => initial ?? EMPTY_PRACTICE);
  const save = useSavePracticeSchedule(fieldId);

  function set<K extends keyof PracticeScheduleEntry>(key: K, value: PracticeScheduleEntry[K]) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  return (
    <Card>
      <h3 className="mb-3 font-medium capitalize">{scenario} scenario</h3>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <FieldLabel>Crop type</FieldLabel>
          <TextInput value={values.crop_type ?? ""} onChange={(e) => set("crop_type", e.target.value)} />
        </div>
        <div>
          <FieldLabel>Tillage depth (cm)</FieldLabel>
          <TextInput type="number" value={values.tillage_depth_cm ?? 0} onChange={(e) => set("tillage_depth_cm", Number(e.target.value))} />
        </div>
        <div>
          <FieldLabel>Residue burned (kg/ha)</FieldLabel>
          <TextInput type="number" value={values.residue_burned_kg_ha ?? 0} onChange={(e) => set("residue_burned_kg_ha", Number(e.target.value))} />
        </div>
        <div>
          <FieldLabel>Synthetic N rate (kg/ha)</FieldLabel>
          <TextInput type="number" value={values.synthetic_n_rate_kg_ha ?? 0} onChange={(e) => set("synthetic_n_rate_kg_ha", Number(e.target.value))} />
        </div>
        <div>
          <FieldLabel>Organic N rate (kg/ha)</FieldLabel>
          <TextInput type="number" value={values.organic_n_rate_kg_ha ?? 0} onChange={(e) => set("organic_n_rate_kg_ha", Number(e.target.value))} />
        </div>
        <div>
          <FieldLabel>Fuel use (L/ha)</FieldLabel>
          <TextInput type="number" value={values.fuel_use_l_ha ?? 0} onChange={(e) => set("fuel_use_l_ha", Number(e.target.value))} />
        </div>
        <div>
          <FieldLabel>Crop yield (t/ha)</FieldLabel>
          <TextInput type="number" value={values.crop_yield_t_ha ?? 0} onChange={(e) => set("crop_yield_t_ha", Number(e.target.value))} />
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-4 text-sm">
        {(["crop_rotation", "cover_crops", "intercropping", "tillage", "residue_removed", "n_fixing_species"] as const).map((key) => (
          <label key={key} className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={Boolean(values[key])}
              onChange={(e) => set(key, e.target.checked)}
            />
            {key.replace(/_/g, " ")}
          </label>
        ))}
      </div>
      <RoleGate allow={["admin", "analyst"]}>
        <Button
          className="mt-4"
          variant="secondary"
          onClick={() => save.mutate({ scenario, practices: values })}
          disabled={save.isPending}
        >
          {save.isPending ? "Saving…" : "Save"}
        </Button>
      </RoleGate>
    </Card>
  );
}

const SOC_LABELS: Array<{ key: "project_t_start" | "project_t_final" | "control_t_start" | "control_t_final"; site: "project" | "control"; timepoint: "t_start" | "t_final"; label: string }> = [
  { key: "project_t_start", site: "project", timepoint: "t_start", label: "Project site — start of period" },
  { key: "project_t_final", site: "project", timepoint: "t_final", label: "Project site — end of period" },
  { key: "control_t_start", site: "control", timepoint: "t_start", label: "Control site — start of period" },
  { key: "control_t_final", site: "control", timepoint: "t_final", label: "Control site — end of period" },
];

function SocMeasurementsForm({ fieldId }: { fieldId: string }) {
  const { data: soc, isLoading } = useSocMeasurements(fieldId);

  if (isLoading || !soc) {
    return (
      <Card>
        <p className="text-sm text-gray-500">Loading SOC measurements…</p>
      </Card>
    );
  }

  return <SocMeasurementsFormBody fieldId={fieldId} soc={soc} />;
}

function SocMeasurementsFormBody({
  fieldId,
  soc,
}: {
  fieldId: string;
  soc: NonNullable<ReturnType<typeof useSocMeasurements>["data"]>;
}) {
  const save = useSaveSocMeasurements(fieldId);
  // `soc` is already resolved by the loading gate above, so this initializer
  // runs once at mount with real data — no effect-based resync needed.
  const [texts, setTexts] = useState<Record<string, string>>(() =>
    Object.fromEntries(SOC_LABELS.map((l) => [l.key, (soc[l.key] ?? []).join("\n")]))
  );

  function handleSave(l: typeof SOC_LABELS[number]) {
    const values = (texts[l.key] ?? "")
      .split("\n")
      .map((s) => parseFloat(s.trim()))
      .filter((v) => !Number.isNaN(v));
    save.mutate({ siteType: l.site, timepoint: l.timepoint, values });
  }

  return (
    <Card>
      <h3 className="mb-1 font-medium">🧫 Soil Organic Carbon Samples</h3>
      <p className="mb-3 text-sm text-gray-500">
        Paired lab measurements (tCO2e/ha) — at least 3 samples per cell required (Eqs. 46-47, 70-71).
      </p>
      <div className="grid grid-cols-2 gap-4">
        {SOC_LABELS.map((l) => {
          const count = (texts[l.key] ?? "").split("\n").filter((s) => s.trim() && !Number.isNaN(parseFloat(s))).length;
          return (
            <div key={l.key}>
              <FieldLabel>{l.label}</FieldLabel>
              <textarea
                value={texts[l.key] ?? ""}
                onChange={(e) => setTexts((t) => ({ ...t, [l.key]: e.target.value }))}
                rows={4}
                placeholder={"40.2\n41.8\n39.5"}
                className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm focus:border-blue-500 focus:outline-none"
              />
              <p className="mt-1 text-xs text-gray-500">{count} sample(s){count < 3 ? " — need ≥ 3" : " ✓"}</p>
              <RoleGate allow={["admin", "analyst"]}>
                <Button variant="secondary" className="mt-1" onClick={() => handleSave(l)} disabled={save.isPending}>
                  Save
                </Button>
              </RoleGate>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export default function PracticeDataPage() {
  const field = useFieldContext();
  const { data: schedule, isLoading } = usePracticeSchedule(field.field_id);

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-lg font-semibold">🧪 Practice &amp; Soil Data</h2>
      {isLoading ? (
        <Card>
          <p className="text-sm text-gray-500">Loading practice schedule…</p>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <PracticeScenarioForm fieldId={field.field_id} scenario="baseline" initial={schedule?.baseline ?? null} />
          <PracticeScenarioForm fieldId={field.field_id} scenario="project" initial={schedule?.project ?? null} />
        </div>
      )}
      <SocMeasurementsForm fieldId={field.field_id} />
    </div>
  );
}
