"use client";

import { FlaskConical, Save } from "lucide-react";
import { useState } from "react";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FieldLabel, Select, TextArea, TextInput } from "@/components/ui/Field";
import { IconTile } from "@/components/ui/IconTile";
import { RoleGate } from "@/components/ui/RoleGate";
import { Skeleton } from "@/components/ui/Skeleton";
import { Switch } from "@/components/ui/Switch";
import { useToast } from "@/components/ui/Toast";
import { usePracticeSchedule, useLivestockSchedule, useSocMeasurements } from "@/hooks/use-alm";
import { useSavePracticeSchedule, useSaveLivestockSchedule, useSaveSocMeasurements } from "@/hooks/use-practice-form";
import { ApiError } from "@/lib/api";
import type { LivestockEntry, PracticeScheduleEntry, ProductivitySystem } from "@/types/api";

function onSaveError(show: (message: string, tone?: "success" | "danger" | "info") => void) {
  return (err: unknown) => show(err instanceof ApiError ? err.detail : "Failed to save", "danger");
}

const LIVESTOCK_TYPE_LABELS: Record<string, string> = {
  cattle_dairy: "Dairy cattle",
  cattle_nondairy: "Non-dairy cattle",
  buffalo: "Buffalo",
  sheep: "Sheep",
  goat: "Goats",
};
const LIVESTOCK_TYPES = Object.keys(LIVESTOCK_TYPE_LABELS);

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
  const { show } = useToast();

  function set<K extends keyof PracticeScheduleEntry>(key: K, value: PracticeScheduleEntry[K]) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  return (
    <Card>
      <h3 className="mb-3 font-medium capitalize text-text-primary">{scenario} scenario</h3>
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
      <div className="mt-4 flex flex-wrap gap-x-6 gap-y-3">
        {(["crop_rotation", "cover_crops", "intercropping", "tillage", "residue_removed", "n_fixing_species"] as const).map((key) => (
          <Switch
            key={key}
            checked={Boolean(values[key])}
            onChange={(checked) => set(key, checked)}
            label={key.replace(/_/g, " ")}
          />
        ))}
      </div>
      <RoleGate allow={["admin", "analyst"]}>
        <Button className="mt-4" variant="secondary" size="sm" icon={Save} loading={save.isPending} onClick={() => save.mutate({ scenario, practices: values }, { onError: onSaveError(show) })}>
          Save
        </Button>
      </RoleGate>
    </Card>
  );
}

function LivestockScenarioForm({
  fieldId,
  scenario,
  initial,
}: {
  fieldId: string;
  scenario: "baseline" | "project";
  initial: LivestockEntry[];
}) {
  // Populations keyed by livestock_type, defaulting every type to 0/low —
  // matches app.py's _alm_practice_form, which renders all 5 types
  // unconditionally and only persists the ones with population > 0.
  const [hasLivestock, setHasLivestock] = useState(initial.length > 0);
  const [rows, setRows] = useState<Record<string, { population: number; productivity: ProductivitySystem }>>(() => {
    const base = Object.fromEntries(
      LIVESTOCK_TYPES.map((t) => [t, { population: 0, productivity: "low" as ProductivitySystem }]),
    );
    for (const e of initial) base[e.livestock_type] = { population: e.population_head, productivity: e.productivity_system };
    return base;
  });
  const save = useSaveLivestockSchedule(fieldId);
  const { show } = useToast();

  function setRow(type: string, patch: Partial<{ population: number; productivity: ProductivitySystem }>) {
    setRows((r) => ({ ...r, [type]: { ...r[type], ...patch } }));
  }

  function handleSave() {
    const entries: LivestockEntry[] = LIVESTOCK_TYPES
      .filter((t) => hasLivestock && rows[t].population > 0)
      .map((t) => ({
        livestock_type: t,
        population_head: rows[t].population,
        productivity_system: rows[t].productivity,
      }));
    save.mutate({ scenario, entries }, { onError: onSaveError(show) });
  }

  return (
    <Card>
      <h3 className="mb-3 font-medium capitalize text-text-primary">{scenario} scenario — livestock</h3>
      <Switch checked={hasLivestock} onChange={setHasLivestock} label="Integrated crop-livestock system (pasture-based grazing)" />
      {hasLivestock && (
        <div className="mt-4 flex flex-col gap-3">
          {LIVESTOCK_TYPES.map((type) => (
            <div key={type} className="grid grid-cols-[1fr_auto_auto] items-end gap-3">
              <div>
                <FieldLabel>{LIVESTOCK_TYPE_LABELS[type]}</FieldLabel>
                <TextInput
                  type="number"
                  min={0}
                  max={500}
                  value={rows[type].population}
                  onChange={(e) => setRow(type, { population: Number(e.target.value) })}
                />
              </div>
              <div>
                <FieldLabel>Productivity</FieldLabel>
                <Select
                  disabled={rows[type].population <= 0}
                  value={rows[type].productivity}
                  onChange={(e) => setRow(type, { productivity: e.target.value as ProductivitySystem })}
                >
                  <option value="low">Low</option>
                  <option value="high">High</option>
                </Select>
              </div>
            </div>
          ))}
        </div>
      )}
      <RoleGate allow={["admin", "analyst"]}>
        <Button className="mt-4" variant="secondary" size="sm" icon={Save} loading={save.isPending} onClick={handleSave}>
          Save
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
    return <Skeleton className="h-48" />;
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
  const { show } = useToast();
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
    save.mutate({ siteType: l.site, timepoint: l.timepoint, values }, { onError: onSaveError(show) });
  }

  return (
    <Card>
      <h3 className="mb-1 flex items-center gap-1.5 font-medium text-text-primary">
        <FlaskConical className="size-4 text-brand-600" />
        Soil Organic Carbon Samples
      </h3>
      <p className="mb-3 text-sm text-text-secondary">
        Paired lab measurements (tCO2e/ha) — at least 3 samples per cell required (Eqs. 46-47, 70-71).
      </p>
      <div className="grid grid-cols-2 gap-4">
        {SOC_LABELS.map((l) => {
          const count = (texts[l.key] ?? "").split("\n").filter((s) => s.trim() && !Number.isNaN(parseFloat(s))).length;
          return (
            <div key={l.key}>
              <FieldLabel>{l.label}</FieldLabel>
              <TextArea
                value={texts[l.key] ?? ""}
                onChange={(e) => setTexts((t) => ({ ...t, [l.key]: e.target.value }))}
                rows={4}
                placeholder={"40.2\n41.8\n39.5"}
              />
              <p className={`mt-1 text-xs ${count < 3 ? "text-warning-700" : "text-text-tertiary"}`}>
                {count} sample(s){count < 3 ? " — need ≥ 3" : " ✓"}
              </p>
              <RoleGate allow={["admin", "analyst"]}>
                <Button variant="secondary" size="sm" icon={Save} className="mt-1" loading={save.isPending} onClick={() => handleSave(l)}>
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
  const { data: livestock, isLoading: livestockLoading } = useLivestockSchedule(field.field_id);

  return (
    <div className="flex flex-col gap-6">
      <h2 className="flex items-center gap-2.5 text-lg font-semibold text-text-primary">
        <IconTile icon={FlaskConical} size="sm" />
        Practice &amp; Soil Data
      </h2>
      {isLoading ? (
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <PracticeScenarioForm fieldId={field.field_id} scenario="baseline" initial={schedule?.baseline ?? null} />
          <PracticeScenarioForm fieldId={field.field_id} scenario="project" initial={schedule?.project ?? null} />
        </div>
      )}
      {livestockLoading ? (
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <LivestockScenarioForm fieldId={field.field_id} scenario="baseline" initial={livestock?.baseline ?? []} />
          <LivestockScenarioForm fieldId={field.field_id} scenario="project" initial={livestock?.project ?? []} />
        </div>
      )}
      <SocMeasurementsForm fieldId={field.field_id} />
    </div>
  );
}
