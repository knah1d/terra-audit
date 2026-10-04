import Link from "next/link";
import { formatDate, formatQueueTimestamp } from "@/lib/format";

export function InputProvenance({ value, fieldId }: { value: unknown; fieldId: string }) {
  const source = value && typeof value === "object" ? value as Record<string, unknown> : null;
  if (!source) return <p className="ui-meta mt-2">This older snapshot has no saved signal-input source link. Do not infer one from the latest analytics.</p>;
  if (source.mode !== "saved_signal") return <p className="ui-meta mt-2">Input source: manual evidence entry.</p>;
  const values = source.source_values && typeof source.source_values === "object" ? source.source_values as Record<string, unknown> : {};
  const overrides = Array.isArray(source.overridden_inputs) ? source.overridden_inputs.map(String) : [];
  return <section className="mt-3 rounded-lg border border-border p-3 space-y-2 text-sm" aria-label="Frozen calculation input provenance">
    <h4 className="ui-subsection-title">Saved input source</h4>
    <p className="break-all">Signal run: {String(source.job_id ?? "—")}</p>
    <p>{formatDate(typeof source.window_start === "string" ? source.window_start : null)} to {formatDate(typeof source.window_end === "string" ? source.window_end : null)} · {String(source.detector ?? "—")} · completed {formatQueueTimestamp(typeof source.finished_at === "string" ? source.finished_at : null)}</p>
    <p>Source values: AWD events {String(values.awd_events ?? "—")}; season length {String(values.season_length_days ?? "—")} days.</p>
    <p>{overrides.length ? `Manual overrides: ${overrides.map(name => name.replaceAll("_", " ")).join(", ")}. The calculation uses the entered values.` : "Both copied inputs match their saved source values."}</p>
    <p className="ui-meta">{String(source.notice ?? "")}</p>
    <Link className="underline text-brand-700" href={`/fields/${encodeURIComponent(fieldId)}/signal-analytics`}>Open field analytics</Link>
  </section>;
}
