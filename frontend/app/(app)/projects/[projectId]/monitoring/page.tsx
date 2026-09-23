"use client";

import { useMemo, useState } from "react";
import { useProjectContext } from "@/components/projects/ProjectContext";
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

export default function ProjectMonitoringPage() {
  const project = useProjectContext();
  const dashboard = useMonitoringDashboard(project.project_id);
  const bulkRun = useBulkRunMonitoring(project.project_id);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [cropFilter, setCropFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

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
    <div className="space-y-5">
      {error && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{error}</p>}
      {notice && <p role="status" className="text-sm text-success-700">{notice}</p>}

      {dashboard.isLoading ? <Skeleton className="h-40" /> : dashboard.data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Field-seasons" value={String(dashboard.data.field_season_count)} />
          <StatCard label="Coverage ready" value={`${dashboard.data.coverage_summary.ready}/${dashboard.data.coverage_summary.total}`} tone="success" />
          <StatCard label="Open issues" value={String(dashboard.data.open_issue_count)} tone={dashboard.data.open_issue_count ? "warning" : "neutral"} />
          <StatCard label="Batches" value={String(dashboard.data.batches.length)} />
        </div>
      )}

      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium">Field-seasons</h3>
          <div className="flex gap-2">
            <TextInput placeholder="Filter by crop" value={cropFilter} onChange={(e) => setCropFilter(e.target.value)} className="max-w-[160px]" />
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="max-w-[180px]">
              <option value="">All statuses</option>
              <option value="ready_for_exploration">Ready</option>
              <option value="insufficient_evidence">Insufficient evidence</option>
              <option value="none">No run yet</option>
            </Select>
          </div>
        </div>
        {!filtered.length ? (
          <EmptyState icon={MapPinned} title="No field-seasons match" description="Assign fields to this project and add crop seasons to see them here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-text-tertiary">
                  <th className="py-1"><input type="checkbox"
                    checked={selected.size > 0 && filtered.every((r) => selected.has(`${r.field_id}:${r.season_id}`))}
                    onChange={(e) => setSelected(e.target.checked ? new Set(filtered.map((r) => `${r.field_id}:${r.season_id}`)) : new Set())} /></th>
                  <th className="py-1">Field</th><th>Season</th><th>Crops</th><th>Latest status</th><th>Source</th><th>Last run</th><th>Issues</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => {
                  const key = `${r.field_id}:${r.season_id}`;
                  return (
                    <tr key={key} className="border-t border-border">
                      <td className="py-1.5"><input type="checkbox" checked={selected.has(key)} onChange={() => toggle(key)} /></td>
                      <td>{r.field_name} <span className="font-mono text-xs text-text-tertiary">{r.field_id}</span></td>
                      <td>{r.season_name}</td>
                      <td>{r.crops.join(", ")}</td>
                      <td>{r.latest_run_status ? (
                        <Badge tone={r.latest_run_status === "ready_for_exploration" ? "success" : "warning"}>
                          {STATUS_LABEL[r.latest_run_status] ?? r.latest_run_status}
                        </Badge>
                      ) : <Badge tone="neutral">no run yet</Badge>}</td>
                      <td>{r.latest_run_source ?? "—"}</td>
                      <td>{r.latest_run_at ? new Date(r.latest_run_at).toLocaleDateString() : "—"}</td>
                      <td>{r.open_issue_count ? <Badge tone="danger">{r.open_issue_count}</Badge> : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="mt-3 flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs"><input type="checkbox" checked={forceRefresh} onChange={(e) => setForceRefresh(e.target.checked)} />Force refresh (skip reuse)</label>
          <Button
            disabled={!selected.size} loading={bulkRun.isPending}
            onClick={() => {
              setError(""); setNotice("");
              const field_seasons = Array.from(selected).map((k) => {
                const [field_id, season_id] = k.split(":");
                return { field_id, season_id };
              });
              bulkRun.mutateAsync({ field_seasons, force_refresh: forceRefresh })
                .then((r) => { setActiveBatchId(r.batch_id); setNotice(`Started batch with ${field_seasons.length} job(s).`); setSelected(new Set()); })
                .catch((e) => setError(e instanceof Error ? e.message : "Failed to start monitoring"));
            }}
          >
            Start monitoring ({selected.size})
          </Button>
        </div>
      </Card>

      <BatchesCard projectId={project.project_id} batches={dashboard.data?.batches ?? []}
                   activeBatchId={activeBatchId} onSelectBatch={setActiveBatchId} />
      <IssuesCard projectId={project.project_id} />
    </div>
  );
}

function BatchesCard({ batches, activeBatchId, onSelectBatch }: {
  projectId: string; batches: { batch_id: string; status: string; total_children: number; created_at: string }[];
  activeBatchId: string | null; onSelectBatch: (id: string) => void;
}) {
  const progress = useBatchProgress(activeBatchId);
  const cancel = useCancelBatch();
  const retry = useRetryFailed();

  return (
    <Card>
      <h3 className="mb-3 font-medium">Batches</h3>
      {!batches.length ? <p className="text-sm text-text-secondary">No monitoring batches yet.</p> : (
        <div className="space-y-1">
          {batches.map((b) => (
            <button key={b.batch_id} onClick={() => onSelectBatch(b.batch_id)}
                    className={`flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-sm ${activeBatchId === b.batch_id ? "bg-brand-50/50" : ""}`}>
              <span><Badge tone={b.status === "completed" ? "success" : b.status === "partial_failure" ? "warning" : "neutral"}>{b.status}</Badge> {b.total_children} job(s) · {new Date(b.created_at).toLocaleString()}</span>
            </button>
          ))}
        </div>
      )}
      {progress.data && (
        <div className="mt-3 rounded-lg bg-surface-muted/40 p-3 text-sm">
          <p className="mb-2 font-medium">Progress: {Object.entries(progress.data.by_status).map(([s, n]) => `${s}: ${n}`).join(" · ")}</p>
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" loading={cancel.isPending} onClick={() => cancel.mutate(activeBatchId!)}>Cancel remaining</Button>
            <Button size="sm" variant="secondary" loading={retry.isPending} onClick={() => retry.mutate(activeBatchId!)}>Retry failed</Button>
          </div>
          <div className="mt-2 space-y-1">
            {progress.data.children.map((c) => (
              <p key={c.job_id} className="text-xs">
                <Badge tone={c.status === "done" ? "success" : c.status === "error" ? "danger" : "neutral"}>{c.status}</Badge>{" "}
                {c.job_id.slice(0, 8)} {c.error ? `— ${c.error}` : ""}
              </p>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function IssuesCard({ projectId }: { projectId: string }) {
  const [statusFilter, setStatusFilter] = useState("open");
  const issues = useProjectIssues(projectId, statusFilter || undefined);
  const acknowledge = useAcknowledgeIssue();
  const resolve = useResolveIssue();
  const [reasonFor, setReasonFor] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-medium">Data-quality issues</h3>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="max-w-xs">
          <option value="open">Open</option><option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option><option value="">All</option>
        </Select>
      </div>
      <p className="mb-2 text-xs text-text-tertiary">
        Provisional engineering screens, not validated accuracy or management-practice compliance claims.
      </p>
      {!issues.data?.length ? <p className="text-sm text-text-secondary">No issues.</p> : (
        <div className="space-y-2">
          {issues.data.map((i) => (
            <div key={i.issue_id} className="border-t border-border py-2 text-sm first:border-t-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={i.severity === "blocking" ? "danger" : "warning"}>{i.issue_type.replace(/_/g, " ")}</Badge>
                <Badge tone="neutral">{i.status}</Badge>
                <span className="font-mono text-xs text-text-tertiary">{i.field_id}</span>
                {i.occurrence_count > 1 && <span className="text-xs text-text-tertiary">×{i.occurrence_count}</span>}
              </div>
              <p className="mt-1">{i.description}</p>
              {i.status !== "resolved" && (
                reasonFor === i.issue_id ? (
                  <form className="mt-2 flex gap-2" onSubmit={(e) => {
                    e.preventDefault();
                    resolve.mutateAsync({ issueId: i.issue_id, reason }).then(() => { setReasonFor(null); setReason(""); });
                  }}>
                    <TextInput value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Resolution reason" required className="flex-1" />
                    <Button type="submit" size="sm" loading={resolve.isPending}>Resolve</Button>
                  </form>
                ) : (
                  <div className="mt-2 flex gap-2">
                    {i.status === "open" && (
                      <Button size="sm" variant="ghost" loading={acknowledge.isPending}
                              onClick={() => acknowledge.mutate({ issueId: i.issue_id })}>Acknowledge</Button>
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
