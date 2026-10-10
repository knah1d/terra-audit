"use client";

import { formatQueueTimestamp } from "@/lib/format";

import { useSearchParams } from "next/navigation";
import Link from "next/link";

import { useMemo, useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { useProjectContext } from "@/components/projects/ProjectContext";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, StatCard } from "@/components/ui/Card";
import { Select, TextInput } from "@/components/ui/Field";
import { EmptyState } from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { MapPinned } from "lucide-react";
import {
  useAcknowledgeIssue, useBatchProgress, useBulkRunMonitoring, useCancelBatch,
  useMonitoringDashboard, useProjectIssues, useResolveIssue, useRetryFailed,
} from "@/hooks/use-monitoring-ops";

const STATUS_LABEL: Record<string, string> = {
  ready_for_exploration: "Ready", insufficient_evidence: "Insufficient evidence",
};
const plain = (value: string) => value.replace(/_/g, " ");

export default function ProjectMonitoringPage() {
  const project = useProjectContext();
  const dashboard = useMonitoringDashboard(project.project_id);
  const bulkRun = useBulkRunMonitoring(project.project_id);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [cropFilter, setCropFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [forceRefresh, setForceRefresh] = useState(false);
  const search = useSearchParams();
  const [activeBatchId, setActiveBatchId] = useState<string | null>(search.get("batch"));
  const toast = useToast();

  const filtered = useMemo(() => (dashboard.data?.fields ?? []).filter((r) =>
    (!cropFilter || r.crops.includes(cropFilter.toLowerCase())) &&
    (!statusFilter || r.latest_run_status === statusFilter || (statusFilter === "none" && !r.latest_run_status))
  ), [dashboard.data, cropFilter, statusFilter]);

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  return (
    <div className="ui-container-wide space-y-6">
      <div>
        <h2 className="ui-section-title">Crop monitoring</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Check satellite coverage of every field&apos;s current crop season in one go, and triage data-quality issues.
          Optional — the AWD inputs for calculations come from each field&apos;s Signal Analytics.
        </p>
      </div>

      {dashboard.error && <Alert tone="danger" title="Could not load monitoring">{dashboard.error.message}</Alert>}
      {dashboard.isLoading ? <Skeleton className="h-40" /> : dashboard.data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Crop seasons" value={String(dashboard.data.field_season_count)} />
          <StatCard label="Coverage ready" value={`${dashboard.data.coverage_summary.ready}/${dashboard.data.coverage_summary.total}`} tone="success" />
          <StatCard label="Open issues" value={String(dashboard.data.open_issue_count)} tone={dashboard.data.open_issue_count ? "warning" : "neutral"} />
          <StatCard label="Monitoring runs" value={String(dashboard.data.batches.length)} />
        </div>
      )}

      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="ui-subsection-title">Current crop seasons</h3>
          <div className="flex gap-2">
            <TextInput aria-label="Filter by crop" placeholder="Filter by crop" value={cropFilter} onChange={(e) => setCropFilter(e.target.value)} className="max-w-[160px]" />
            <Select aria-label="Monitoring status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="max-w-[180px]">
              <option value="">All statuses</option>
              <option value="ready_for_exploration">Ready</option>
              <option value="insufficient_evidence">Insufficient evidence</option>
              <option value="none">No run yet</option>
            </Select>
          </div>
        </div>
        {dashboard.isLoading ? <Skeleton className="h-24" /> : dashboard.error ? null : !filtered.length ? (
          <EmptyState icon={MapPinned} title="No crop seasons match"
            description={dashboard.data?.fields.length ? "Change the filters to see more." : "Assign fields to this project and add crop seasons to see them here."} />
        ) : (
          <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Field season monitoring table; scroll horizontally for all columns">
            <table className="w-full min-w-[760px] text-sm [&_td]:px-2 [&_th]:px-2">
              <caption className="sr-only">Current crop seasons, monitoring runs and outstanding issues</caption>
              <thead>
                <tr className="ui-meta text-left">
                  <th scope="col" className="py-1">{project.can_contribute && <input type="checkbox" aria-label="Select all crop seasons"
                    checked={selected.size > 0 && filtered.every((r) => selected.has(`${r.field_id}:${r.season_id}`))}
                    onChange={(e) => setSelected(e.target.checked ? new Set(filtered.map((r) => `${r.field_id}:${r.season_id}`)) : new Set())} />}</th>
                  <th scope="col" className="py-1">Field</th><th scope="col">Season</th><th scope="col">Crops</th><th scope="col">Latest status</th><th scope="col">Source</th><th scope="col">Last run</th><th scope="col">Issues</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => {
                  const key = `${r.field_id}:${r.season_id}`;
                  return (
                    <tr key={key} className="border-t border-border">
                      <td className="py-1.5">{project.can_contribute && <input type="checkbox" aria-label={`Select ${r.field_name}, ${r.season_name}`} checked={selected.has(key)} onChange={() => toggle(key)} />}</td>
                      <td><Link className="underline" href={`/fields/${r.field_id}/overview`}>{r.field_name}</Link></td>
                      <td><Link className="underline" href={`/fields/${r.field_id}/crop-seasons?season=${r.season_id}`}>{r.season_name}</Link></td>
                      <td>{r.crops.join(", ")}</td>
                      <td>{r.latest_run_status ? (
                        <Badge tone={r.latest_run_status === "ready_for_exploration" ? "success" : "warning"}>
                          {STATUS_LABEL[r.latest_run_status] ?? r.latest_run_status}
                        </Badge>
                      ) : <Badge tone="neutral">no run yet</Badge>}</td>
                      <td>{r.latest_run_source ? plain(r.latest_run_source) : "—"}</td>
                      <td>{formatQueueTimestamp(r.latest_run_at)}</td>
                      <td>{r.open_issue_count ? <Badge tone="danger">{r.open_issue_count}</Badge> : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {project.can_contribute && <div className="mt-3 flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs"><input type="checkbox" checked={forceRefresh} onChange={(e) => setForceRefresh(e.target.checked)} />Re-run even if a recent result exists</label>
          <Button
            disabled={!selected.size} loading={bulkRun.isPending}
            onClick={() => {
              const field_seasons = Array.from(selected).map((k) => {
                const [field_id, season_id] = k.split(":");
                return { field_id, season_id };
              });
              bulkRun.mutateAsync({ field_seasons, force_refresh: forceRefresh })
                .then((r) => { setActiveBatchId(r.batch_id); toast.success("Monitoring started", { description: `${field_seasons.length} crop season(s) queued.` }); setSelected(new Set()); })
                .catch((e) => toast.error(e, "Failed to start monitoring"));
            }}
          >
            Start monitoring ({selected.size})
          </Button>
        </div>}
      </Card>

      <BatchesCard projectId={project.project_id} batches={dashboard.data?.batches ?? []} canAct={project.can_contribute}
                   activeBatchId={activeBatchId} onSelectBatch={setActiveBatchId} />
      <IssuesCard projectId={project.project_id} canAct={project.can_contribute}
                  fieldName={(id) => dashboard.data?.fields.find((f) => f.field_id === id)?.field_name ?? "Field"} />
    </div>
  );
}

function BatchesCard({ batches, activeBatchId, onSelectBatch, canAct }: {
  projectId: string; batches: { batch_id: string; status: string; total_children: number; created_at: string }[];
  activeBatchId: string | null; onSelectBatch: (id: string) => void; canAct: boolean;
}) {
  const progress = useBatchProgress(activeBatchId);
  const cancel = useCancelBatch();
  const retry = useRetryFailed();
  const toast = useToast();
  const children = progress.data?.children ?? [];
  const cancellable = children.some((c) => ["pending", "running", "cancel_requested"].includes(c.status));
  const retryable = children.some((c) => c.status === "error");

  return (
    <Card>
      <h3 className="ui-subsection-title mb-3">Monitoring runs</h3>
      {!batches.length ? <p className="ui-secondary">No monitoring runs yet.</p> : (
        <div className="space-y-1">
          {batches.map((b) => (
            <button key={b.batch_id} type="button" onClick={() => onSelectBatch(b.batch_id)} aria-pressed={activeBatchId === b.batch_id}
                    className={`flex min-h-11 w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${activeBatchId === b.batch_id ? "border-brand-600 bg-brand-50" : "border-transparent hover:bg-surface-muted"}`}>
              <span><Badge tone={b.status === "completed" ? "success" : b.status === "partial_failure" ? "warning" : "neutral"}>{plain(b.status)}</Badge> {b.total_children} crop season(s) · {formatQueueTimestamp(b.created_at)}</span>
            </button>
          ))}
        </div>
      )}
      {progress.data && (
        <div className="mt-3 rounded-lg bg-surface-muted/40 p-3 text-sm">
          <p className="mb-2 font-medium">Progress: {Object.entries(progress.data.by_status).map(([s, n]) => `${plain(s)}: ${n}`).join(" · ")}</p>
          {canAct && (cancellable || retryable) && <div className="flex gap-2">
            {cancellable && <Button size="sm" variant="secondary" loading={cancel.isPending} onClick={() => cancel.mutateAsync(activeBatchId!)
              .then(() => toast.success("Remaining runs cancelled")).catch((e) => toast.error(e, "Couldn't cancel"))}>Cancel remaining</Button>}
            {retryable && <Button size="sm" variant="secondary" loading={retry.isPending} onClick={() => retry.mutateAsync(activeBatchId!)
              .then(() => toast.success("Failed runs queued again")).catch((e) => toast.error(e, "Couldn't retry"))}>Retry failed</Button>}
          </div>}
          <div className="mt-2 space-y-1">
            {progress.data.children.map((c) => (
              <p key={c.job_id} className="text-xs">
                <Badge tone={c.status === "done" ? "success" : c.status === "error" ? "danger" : "neutral"}>{plain(c.status)}</Badge>{" "}
                {c.error ?? ""}
              </p>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function IssuesCard({ projectId, canAct, fieldName }: { projectId: string; canAct: boolean; fieldName: (id: string) => string }) {
  const [statusFilter, setStatusFilter] = useState("open");
  const issues = useProjectIssues(projectId, statusFilter || undefined);
  const acknowledge = useAcknowledgeIssue();
  const resolve = useResolveIssue();
  const [reasonFor, setReasonFor] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const toast = useToast();

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="ui-subsection-title">Data-quality issues</h3>
        <Select aria-label="Issue status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="max-w-xs">
          <option value="open">Open</option><option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option><option value="">All</option>
        </Select>
      </div>
      <p className="ui-meta mb-2">
        Automatic checks on the satellite data (for example, too few images). They flag gaps to look at; they do not judge farm practice.
      </p>
      {issues.isLoading ? <Skeleton className="h-16" /> : issues.error ? (
        <Alert tone="danger" title="Could not load issues">{issues.error.message}</Alert>
      ) : !issues.data?.length ? <p className="ui-secondary">No issues.</p> : (
        <div className="space-y-2">
          {issues.data.map((i) => (
            <div key={i.issue_id} className="border-t border-border py-2 text-sm first:border-t-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={i.severity === "blocking" ? "danger" : "warning"}>{i.issue_type.replace(/_/g, " ")}</Badge>
                <Badge tone="neutral">{i.status}</Badge>
                <Link className="text-xs underline" href={`/fields/${encodeURIComponent(i.field_id)}/overview`}>{fieldName(i.field_id)}</Link>
                {i.occurrence_count > 1 && <span className="ui-meta">×{i.occurrence_count}</span>}
              </div>
              <p className="mt-1">{i.description}</p>
              {canAct && i.status !== "resolved" && (
                reasonFor === i.issue_id ? (
                  <form className="mt-2 flex gap-2" onSubmit={(e) => {
                    e.preventDefault();
                    resolve.mutateAsync({ issueId: i.issue_id, reason })
                      .then(() => { setReasonFor(null); setReason(""); toast.success("Issue resolved"); })
                      .catch((err) => toast.error(err, "Couldn't resolve the issue"));
                  }}>
                    <TextInput aria-label="Reason for resolving this issue" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Resolution reason" required className="flex-1" />
                    <Button type="submit" size="sm" loading={resolve.isPending}>Resolve</Button>
                  </form>
                ) : (
                  <div className="mt-2 flex gap-2">
                    {i.status === "open" && (
                      <Button size="sm" variant="ghost" loading={acknowledge.isPending}
                              onClick={() => acknowledge.mutateAsync({ issueId: i.issue_id })
                                .then(() => toast.success("Issue acknowledged")).catch((err) => toast.error(err, "Couldn't acknowledge the issue"))}>Acknowledge</Button>
                    )}
                    <Button size="sm" variant="secondary" onClick={() => setReasonFor(i.issue_id)}>Resolve…</Button>
                  </div>
                )
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
