"use client";

import { useQuery } from "@tanstack/react-query";
import { FileArchive, FileDown } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ProjectDocuments } from "@/components/projects/ProjectDocuments";
import { useProjectContext } from "@/components/projects/ProjectContext";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, StatCard } from "@/components/ui/Card";
import { TextInput } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { apiFetch, apiFetchBlob } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { formatDate, formatNumber } from "@/lib/format";

type MrvSummary = {
  status: "final" | "draft";
  period_start: string;
  period_end: string;
  net_tco2e: number;
  included: {
    calculation_id: string; version: number; field_id: string; field_name: string; area_ha: number;
    period_start: string; period_end: string; net_tco2e: number | null; review_status: string; submission_id: string | null;
  }[];
  excluded: { field_id: string; name: string; reason: string }[];
};

const REVIEW_TONE: Record<string, "success" | "brand" | "warning" | "danger" | "neutral"> = {
  internally_approved: "success", submitted: "brand", in_review: "brand",
  changes_requested: "warning", rejected: "danger", not_submitted: "neutral",
};

/** Project-level VM0051 monitoring report and the verifier evidence package
 * (backend/routers/export.py): every field's current reviewable calculation
 * in the chosen period. Final once every included field is internally approved. */
export default function ProjectMrvPage() {
  const project = useProjectContext();
  const toast = useToast();
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [downloading, setDownloading] = useState<"pdf" | "zip" | null>(null);
  const base = `/projects/${encodeURIComponent(project.project_id)}/mrv`;
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const qs = params.size ? `?${params}` : "";
  const summary = useQuery({ queryKey: ["project-mrv", project.project_id, start, end], queryFn: () => apiFetch<MrvSummary>(`${base}${qs}`) });

  async function download(kind: "pdf" | "zip") {
    setDownloading(kind);
    try {
      const blob = await apiFetchBlob(`${base}/${kind === "pdf" ? "report.pdf" : "package.zip"}${qs}`);
      downloadBlob(blob, kind === "pdf" ? `project-mrv-report-${project.project_id}.pdf` : `mrv-package-${project.project_id}.zip`);
    } catch (e) {
      toast.error(e, "Download failed");
    } finally {
      setDownloading(null);
    }
  }

  const data = summary.data;
  if (project.pathways.length && !project.pathways.includes("vm0051_rice_awd")) {
    return <div className="ui-container"><Alert tone="info" title="MRV report not available">
      The project MRV report covers rice fields under VM0051. For cropland (VM0042), download each calculation&apos;s report from its Calculations tab.
    </Alert></div>;
  }
  return (
    <div className="ui-container space-y-6">
      <Card className="space-y-3">
        <div>
          <h2 className="ui-section-title">MRV report</h2>
          <p className="ui-secondary">VM0051 monitoring report for the whole project, with an evidence package for the verifier (VVB).</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">Period from<TextInput type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
          <label className="text-sm">Period to<TextInput type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        </div>
        <p className="ui-meta">Leave both empty to include every saved monitoring period.</p>
      </Card>

      {summary.isLoading ? <Skeleton className="h-48" /> : summary.error ? (
        <Alert tone="danger" title="Could not load the report scope">{summary.error.message}</Alert>
      ) : data && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard label="Net reductions (tCO2e)" value={formatNumber(data.net_tco2e, "tco2e")} tone="success" />
            <StatCard label="Fields reported" value={String(data.included.length)} />
            <StatCard label="Monitoring period" value={data.included.length ? `${formatDate(data.period_start)} – ${formatDate(data.period_end)}` : "—"} />
          </div>

          <Card className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Badge tone={data.status === "final" ? "success" : "warning"}>{data.status === "final" ? "Final" : "Draft"}</Badge>
                <span className="text-sm text-text-secondary">
                  {data.status === "final" ? "Every included field is internally approved — ready for the verifier."
                    : "Becomes final when every included field's calculation is internally approved."}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button icon={FileDown} variant={data.status === "final" ? "primary" : "secondary"} disabled={!data.included.length || !!downloading}
                  loading={downloading === "pdf"} onClick={() => void download("pdf")}>Report (PDF)</Button>
                <Button icon={FileArchive} variant={data.status === "final" ? "primary" : "secondary"} disabled={!data.included.length || !!downloading}
                  loading={downloading === "zip"} onClick={() => void download("zip")}>Evidence package (ZIP)</Button>
              </div>
            </div>

            {data.included.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-text-secondary">
                    <tr><th className="py-2 pr-3 font-medium">Field</th><th className="py-2 pr-3 font-medium">Period</th>
                      <th className="py-2 pr-3 font-medium">Net tCO2e</th><th className="py-2 font-medium">Internal review</th></tr>
                  </thead>
                  <tbody>
                    {data.included.map((row) => (
                      <tr key={row.calculation_id} className="border-t border-border">
                        <td className="py-2 pr-3"><Link className="underline" href={`/fields/${encodeURIComponent(row.field_id)}/calculations`}>{row.field_name}</Link>
                          <span className="ml-1 text-text-tertiary">v{row.version} · {row.area_ha.toFixed(2)} ha</span></td>
                        <td className="py-2 pr-3">{formatDate(row.period_start)} – {formatDate(row.period_end)}</td>
                        <td className="py-2 pr-3 font-mono">{formatNumber(row.net_tco2e, "tco2e")}</td>
                        <td className="py-2">
                          {row.submission_id
                            ? <Link href={`/reviews/${encodeURIComponent(row.submission_id)}`}><Badge tone={REVIEW_TONE[row.review_status] ?? "neutral"}>{row.review_status.replace(/_/g, " ")}</Badge></Link>
                            : <Badge tone="neutral">not submitted</Badge>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="ui-secondary">No field has a calculation ready for review in this period. Save one from a field&apos;s Calculations tab.</p>
            )}
          </Card>

          {!!data.excluded.length && (
            <Card>
              <h3 className="ui-subsection-title mb-2">Not included</h3>
              <ul className="space-y-1.5 text-sm">
                {data.excluded.map((e) => (
                  <li key={e.field_id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>{e.name} — <span className="text-text-secondary">{e.reason}</span></span>
                    <Link className="font-medium underline" href={`/fields/${encodeURIComponent(e.field_id)}/calculations`}>Open calculations</Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}

      <ProjectDocuments project={project} />
    </div>
  );
}
