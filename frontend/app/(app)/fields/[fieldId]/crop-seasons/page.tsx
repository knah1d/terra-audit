"use client";

import { useSearchParams } from "next/navigation";
import { SeasonHistory } from "@/components/evidence/SeasonHistory";
import { formatDate } from "@/lib/format";
import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/app/providers";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput } from "@/components/ui/Field";
import { useCropSeasons } from "@/hooks/use-crop-seasons";
import { apiFetch } from "@/lib/api";

type RecordRow<T> = { id: string; season_id: string; created_at: string; payload: T };
type Season = {
  name: string; crops: string[]; start_date: string; end_date: string; notes: string;
  season_type?: string; is_historical?: boolean; fallow_reason?: string; missing_period_reason?: string;
  crop_sequence?: { crop: string; start_date: string; end_date: string }[];
};

export default function CropSeasonsPage() {
  const field = useFieldContext();
  const params = useSearchParams();
  return <CropSeasonsView key={`${field.field_id}:${params.toString()}`} />;
}

function CropSeasonsView() {
  const field = useFieldContext();
  const session = useSession();
  const writable = session?.role === "admin" || session?.role === "analyst";
  const queryClient = useQueryClient();
  const base = `/fields/${encodeURIComponent(field.field_id)}/crop-seasons`;
  const search = useSearchParams();
  const [selected, setSelected] = useState(search.get("season") ?? "");
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [seasonType, setSeasonType] = useState("single_crop");
  const [isHistorical, setIsHistorical] = useState(false);
  const [cropSequence, setCropSequence] = useState<{ crop: string; start_date: string; end_date: string }[]>([]);
  const seasons = useCropSeasons(field.field_id);
  const seasonId = seasons.data?.some(s => s.id === selected) ? selected : seasons.data?.[0]?.id || "";

  async function perform(action: () => Promise<void>) {
    setBusy(true);
    try { await action(); } catch (e) { toast.error(e, "Couldn't save"); }
    finally { setBusy(false); }
  }


  return <div className="ui-container space-y-6">
    <div>
      <h2 className="ui-section-title">Crop seasons</h2>
    </div>
    {seasons.error && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{seasons.error.message}</p>}
    {writable && <Card>
      <h3 className="ui-subsection-title mb-3">Add a crop season</h3>
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={e => {
        e.preventDefault(); const form = e.currentTarget; const data = new FormData(form);
        const isGap = seasonType === "fallow" || seasonType === "missing_period";
        void perform(async () => {
          const row = await apiFetch<RecordRow<Season>>(base, { method: "POST", json: {
            name: data.get("name"),
            crops: isGap ? [] : String(data.get("crops")).split(","),
            start_date: data.get("start_date"), end_date: data.get("end_date"), notes: data.get("notes"),
            season_type: seasonType, is_historical: isHistorical,
            fallow_reason: seasonType === "fallow" ? data.get("fallow_reason") : "",
            missing_period_reason: seasonType === "missing_period" ? data.get("missing_period_reason") : "",
            crop_sequence: (seasonType === "rotation" || seasonType === "intercrop") ? cropSequence : [],
          } });
          setSelected(row.id); form.reset(); setSeasonType("single_crop"); setIsHistorical(false); setCropSequence([]);
          await queryClient.invalidateQueries({ queryKey: ["crop-seasons", field.field_id] });
          toast.success("Crop season saved");
        });
      }}>
        <label className="text-sm">Season name<TextInput name="name" required maxLength={120} placeholder="Winter 2025–26" /></label>
        <label className="text-sm">Season type
          <Select value={seasonType} onChange={e => setSeasonType(e.target.value)}>
            <option value="single_crop">Single crop</option>
            <option value="rotation">Rotation (multiple crops in sequence)</option>
            <option value="intercrop">Intercrop (crops grown together)</option>
            <option value="cover_crop">Cover crop</option>
            <option value="fallow">Fallow (documented, no crop)</option>
            <option value="missing_period">Missing period (records unavailable)</option>
          </Select>
        </label>
        {seasonType !== "fallow" && seasonType !== "missing_period" && (
          <label className="text-sm">Crops, separated by commas<TextInput name="crops" required placeholder="Wheat, lentil" /></label>
        )}
        <label className="text-sm">Start date<TextInput name="start_date" type="date" required /></label>
        <label className="text-sm">End date (inclusive)<TextInput name="end_date" type="date" required /></label>
        {seasonType === "fallow" && (
          <label className="text-sm sm:col-span-2">Fallow reason (required)<TextInput name="fallow_reason" required maxLength={500} placeholder="e.g. field rested between rice seasons" /></label>
        )}
        {seasonType === "missing_period" && (
          <label className="text-sm sm:col-span-2">Why records are unavailable (required)<TextInput name="missing_period_reason" required maxLength={500} placeholder="e.g. farmer records lost for this year" /></label>
        )}
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={isHistorical} onChange={e => setIsHistorical(e.target.checked)} />
          This is historical/baseline evidence (predates the monitored project period), not a monitored project-period season.
        </label>
        <label className="text-sm sm:col-span-2">Notes<TextInput name="notes" maxLength={2000} /></label>
        {(seasonType === "rotation" || seasonType === "intercrop") && (
          <div className="sm:col-span-2 space-y-2 rounded-lg border border-border-subtle p-3">
            <p className="text-sm font-medium">
              {seasonType === "rotation" ? "Crop sequence (sequential cycles within this season)" : "Intercropped commodities"}
            </p>
            {cropSequence.map((entry, i) => (
              <div key={i} className="grid gap-2 sm:grid-cols-4">
                <TextInput
                  aria-label={`Crop for sequence entry ${i + 1}`} required placeholder="Crop" value={entry.crop}
                  onChange={e => setCropSequence(seq => seq.map((s, j) => j === i ? { ...s, crop: e.target.value } : s))}
                />
                <TextInput
                  aria-label={`Start date for sequence entry ${i + 1}`} required type="date" value={entry.start_date}
                  onChange={e => setCropSequence(seq => seq.map((s, j) => j === i ? { ...s, start_date: e.target.value } : s))}
                />
                <TextInput
                  aria-label={`End date for sequence entry ${i + 1}`} required type="date" value={entry.end_date}
                  onChange={e => setCropSequence(seq => seq.map((s, j) => j === i ? { ...s, end_date: e.target.value } : s))}
                />
                <Button type="button" variant="ghost" onClick={() => setCropSequence(seq => seq.filter((_, j) => j !== i))} aria-label={`Remove sequence entry ${i + 1}`}>Remove</Button>
              </div>
            ))}
            <Button
              type="button" variant="secondary"
              onClick={() => setCropSequence(seq => [...seq, { crop: "", start_date: "", end_date: "" }])}
            >
              Add {seasonType === "rotation" ? "cycle" : "commodity"}
            </Button>
          </div>
        )}
        <div><Button loading={busy} type="submit">Save season</Button></div>
      </form>
    </Card>}
    {seasons.isLoading ? <p role="status">Loading seasons…</p> : !seasons.data?.length ? <Card>No crop seasons recorded yet.</Card> : <>
      <label className="ui-label block">Selected season<Select value={seasonId} onChange={e => setSelected(e.target.value)}>
        {seasons.data.map(s => <option key={s.id} value={s.id}>{s.payload.name} · {s.payload.crops.join(" + ")} · {formatDate(s.payload.start_date)} to {formatDate(s.payload.end_date)}</option>)}
      </Select></label>
      <SeasonHistory key={seasonId} fieldId={field.field_id} seasonId={seasonId} writable={writable} />
    </>}
  </div>;
}
