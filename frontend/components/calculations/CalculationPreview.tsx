"use client";

import { Sheet } from "@/components/ui/Sheet";
import { formatDate } from "@/lib/format";

type Values = Record<string, unknown>;

const num = (v: unknown, digits = 2) =>
  typeof v === "number" && Number.isFinite(v) ? v.toLocaleString(undefined, { maximumFractionDigits: digits }) : "—";
const PRESEASON: Record<string, string> = {
  short: "Non-flooded < 180 days (double/multi-cropping)", long: "Non-flooded > 180 days (single cropping)",
};

function Row({ label, value, note }: { label: string; value: React.ReactNode; note?: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 border-t border-border py-1.5 text-sm first:border-t-0">
      <span className="text-text-secondary">{label}{note && <span className="ui-meta"> · {note}</span>}</span>
      <span className="text-right font-mono tabular-nums">{value}</span>
    </div>
  );
}

function Step({ n, title, formula, value, strong }: { n: number; title: string; formula: string; value: string; strong?: boolean }) {
  return (
    <li className={`rounded-lg border p-3 ${strong ? "border-brand-600 bg-brand-50" : "border-border"}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-medium">{n}. {title}</span>
        <span className={`font-mono tabular-nums ${strong ? "text-lg font-semibold text-brand-700" : ""}`}>{value}</span>
      </div>
      <p className="mt-1 break-words font-mono text-xs text-text-secondary">{formula}</p>
    </li>
  );
}

/** Pop-up with the whole calculation: what went in, the factors used, and each
 * VM0051 step with the engine's own numbers (nothing is recomputed here). */
export function CalculationPreview({ open, onClose, result, inputs, context }: {
  open: boolean; onClose: () => void; result: Values; inputs: Values;
  context: { field: string; areaHa: number | null; start: string; end: string; seasons: string; project: string; isRice: boolean };
}) {
  const r = result;
  const area = context.areaHa ?? 0;
  const amendment = (inputs.project_amendments as [string, number][] | undefined)?.[0];
  const days = inputs.season_length_days;
  const ef = r.ef_c_used;

  return (
    <Sheet open={open} onClose={onClose} title="Full calculation">
      <div className="max-h-[75vh] space-y-5 overflow-y-auto pr-1 text-sm">
        <section>
          <h3 className="ui-subsection-title mb-1">Context</h3>
          <Row label="Field" value={context.field} />
          <Row label="Area" value={`${num(area, 4)} ha`} />
          <Row label="Monitoring period" value={`${formatDate(context.start)} – ${formatDate(context.end)}`} />
          <Row label="Crop season(s)" value={context.seasons || "—"} />
          <Row label="Project" value={context.project} />
        </section>

        {context.isRice ? <>
          <section>
            <h3 className="ui-subsection-title mb-1">Inputs</h3>
            <Row label="AWD (drainage) events" value={num(inputs.awd_events, 0)} />
            <Row label="Season length" value={`${num(days, 0)} days`} />
            <Row label="Pre-season water regime" value={PRESEASON[String(inputs.preseason_category)] ?? String(inputs.preseason_category ?? "—")} />
            <Row label="Synthetic N input (Q_N)" value={`${num(inputs.q_n_kg_per_ha, 1)} kg N/ha`} />
            <Row label="Organic amendment" value={amendment ? `${String(amendment[0]).replace(/_/g, " ")} · ${num(amendment[1], 2)} t/ha` : "—"} />
          </section>

          <section>
            <h3 className="ui-subsection-title mb-1">Factors (VM0051 v1.1, QA3)</h3>
            <Row label="Emission factor EF_c" value={`${num(ef, 3)} kg CH₄/ha/day`} note="IPCC 2019 Table 5.11" />
            <Row label="Water regime SF_w, baseline" value="1.00" note="continuous flooding" />
            <Row label="Water regime SF_w, project" value={num(r.sf_w_project, 2)} note="Table 5.12, from the AWD events" />
            <Row label="Pre-season SC_p" value={num(r.sc_preseason, 2)} note="Table 5.13" />
            <Row label="Organic amendment SC_o, baseline / project" value={`${num(r.sc_organic_bsl, 4)} / ${num(r.sc_organic_wp, 4)}`} note="Eq. 7" />
            <Row label="GWP CH₄ / N₂O" value="28 / 265" note="IPCC AR5" />
          </section>

          <section>
            <h3 className="ui-subsection-title mb-2">Step by step</h3>
            {r.qa3_pathway_valid === false ? (
              <p className="rounded-lg bg-danger-50 p-3 text-danger-700">{String(r.qa3_block_reason ?? "The QA3 pathway is not valid for this result.")}</p>
            ) : (
              <ol className="space-y-2">
                <Step n={1} title="Baseline methane" value={`${num(r.e_baseline)} kg CH₄`}
                  formula={`EF_c × 1.00 × SC_p × SC_o,b × days × area = ${num(ef, 3)} × 1.00 × ${num(r.sc_preseason, 2)} × ${num(r.sc_organic_bsl, 4)} × ${num(days, 0)} × ${num(area, 4)}`} />
                <Step n={2} title="Project methane (with AWD)" value={`${num(r.e_project)} kg CH₄`}
                  formula={`EF_c × SF_w × SC_p × SC_o,p × days × area = ${num(ef, 3)} × ${num(r.sf_w_project, 2)} × ${num(r.sc_preseason, 2)} × ${num(r.sc_organic_wp, 4)} × ${num(days, 0)} × ${num(area, 4)}`} />
                <Step n={3} title="Methane avoided" value={`${num(r.delta_e_ch4)} kg CH₄`}
                  formula={`baseline − project = ${num(r.e_baseline)} − ${num(r.e_project)}`} />
                <Step n={4} title="Gross reductions" value={`${num(r.delta_e_co2e, 4)} tCO₂e`}
                  formula={`CH₄ avoided × 28 ÷ 1000 = ${num(r.delta_e_ch4)} × 28 ÷ 1000`} />
                <Step n={5} title="Uncertainty deduction (15%)" value={`− ${num(r.unc_tco2e, 4)} tCO₂e`}
                  formula={`gross × 0.15 = ${num(r.delta_e_co2e, 4)} × 0.15 → ${num(r.ch4_after_unc, 4)} tCO₂e left`} />
                <Step n={6} title="N₂O correction (Eq. 25)" value={`− ${num(r.pe_n2o_tco2e, 4)} tCO₂e`}
                  formula={`Q_N × area × 0.00314 × 265 ÷ 1000 = ${num(inputs.q_n_kg_per_ha, 1)} × ${num(area, 4)} × 0.00314 × 265 ÷ 1000`} />
                <Step n={7} title="Net emission reductions (Eq. 29)" value={`${num(r.final_issuance, 4)} tCO₂e`} strong
                  formula={`after uncertainty − N₂O = ${num(r.ch4_after_unc, 4)} − ${num(r.pe_n2o_tco2e, 4)} (never below 0)`} />
              </ol>
            )}
          </section>
        </> : (
          <section>
            <h3 className="ui-subsection-title mb-1">Result values</h3>
            {Object.entries(r).filter(([, v]) => typeof v === "number").map(([k, v]) => (
              <Row key={k} label={k.replace(/_/g, " ")} value={num(v, 4)} />
            ))}
          </section>
        )}

        <p className="ui-meta">Calculated estimate — not issued credits. Every value above comes from the calculation engine for these inputs.</p>
      </div>
    </Sheet>
  );
}
