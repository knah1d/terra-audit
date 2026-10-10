"use client";
import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { RoleGate } from "@/components/ui/RoleGate";
import { Skeleton } from "@/components/ui/Skeleton";
import { useQueueStatus } from "@/hooks/use-monitoring-ops";
import { formatQueueTimestamp } from "@/lib/format";
import { useSession } from "@/app/providers";

export default function QueueStatusPage() {
  const session = useSession();
  const queue = useQueueStatus(session?.role === "admin");
  const alive = queue.data?.workers.some(worker => worker.health === "alive");
  function sourceRoute(job: NonNullable<NonNullable<typeof queue.data>["recent_jobs"]>[number]) {
    if (job.job_type === "methodology_ingest") return "/admin/setup";
    if (!job.field_id) return job.project_id ? `/projects/${encodeURIComponent(job.project_id)}/ai` : null;
    const section = job.job_type === "ai_explain" ? "calculations" : job.job_type === "multicrop_monitoring" ? "crop-seasons" : job.job_type === "signal_run" ? "signal-analytics" : "calculations";
    const params = new URLSearchParams();
    if (job.project_id) params.set("project", job.project_id);
    if (job.requirement_id) params.set("requirement", job.requirement_id);
    if (job.monitoring_period_start) params.set("start", job.monitoring_period_start);
    if (job.monitoring_period_end) params.set("end", job.monitoring_period_end);
    for (const season of job.season_ids ?? []) params.append("season", season);
    return `/fields/${encodeURIComponent(job.field_id)}/${section}${params.size ? `?${params}` : ""}`;
  }
  return (
    <RoleGate allow={["admin"]} fallback={<Alert tone="danger" title="Admins only">You don&apos;t have access to this page.</Alert>}>
      <div className="ui-container space-y-6">
        <PageHeader title="Worker & queue status" subtitle="Operational visibility into the durable job queue — not tenant data." />
        <div className="flex flex-wrap items-center gap-3"><Button variant="secondary" size="sm" loading={queue.isFetching} onClick={() => void queue.refetch()}>Refresh status</Button><span className="ui-meta">Refreshes every 10 seconds while this page is active.</span></div>
        {queue.data && !alive && <Alert tone="warning" title="No recent worker heartbeat">Queued work may wait until a worker reconnects. Start the worker against the same database as the API. A worker started with --job-types ai_explain will not process signal analytics.</Alert>}
        {queue.error && <Alert tone="danger" title="Queue unavailable">{queue.error.message}</Alert>}
        {queue.isLoading ? <Skeleton className="h-40" /> : queue.data && (
          <>
            <Card>
              <h3 className="ui-subsection-title mb-2">Jobs by status</h3>
              <div className="flex flex-wrap gap-2">
                {Object.entries(queue.data.by_status).map(([s, n]) => (
                  <Badge key={s} tone={s === "error" ? "danger" : s === "pending" ? "warning" : "neutral"}>{s}: {n}</Badge>
                ))}
              </div>
              {queue.data.oldest_pending_since && (
                <p className="ui-meta mt-2">Oldest pending job since {formatQueueTimestamp(queue.data.oldest_pending_since)}</p>
              )}
            </Card>
            <Card>
              <h3 className="ui-subsection-title mb-2">Workers</h3><p className="ui-secondary mb-2">A recent heartbeat confirms connection, not that this worker accepts every job type or that a particular job is progressing.</p>
              <p className="ui-meta mb-2">Times are shown in your browser&apos;s local timezone. A worker is stale after two minutes without a heartbeat.</p>
              {!queue.data.workers.length ? <p className="ui-secondary">No workers have registered yet — start one with `python -m backend.worker`.</p> : (
                <div className="space-y-1 text-sm">
                  {queue.data.workers.map((w) => (
                    <p key={w.worker_id}>
                      <Badge tone={w.health === "alive" ? "success" : w.health === "stale" ? "warning" : "neutral"}>{w.health ?? "unknown"}</Badge>{" "}
                      {w.hostname} · last heartbeat {formatQueueTimestamp(w.last_heartbeat_at)}
                    </p>
                  ))}
                </div>
              )}
            </Card>
            <Card><h3 className="ui-subsection-title mb-3">Work by job type</h3><div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Operational queue counts by job type and state</caption><thead><tr><th scope="col" className="py-2 pr-4">Job type</th><th scope="col" className="pr-4">State</th><th scope="col">Count</th></tr></thead><tbody>{queue.data.by_type.map(row => <tr key={`${row.job_type}:${row.status}`} className="border-t border-border"><th scope="row" className="py-2 pr-4 font-medium">{row.job_type}</th><td className="pr-4">{row.status}</td><td>{row.n}</td></tr>)}</tbody></table></div></Card>
            <Card><h3 className="ui-subsection-title mb-3">Recent jobs in your organization</h3><p className="ui-meta mb-3">Failed jobs keep their error. Return to the source, check current evidence and configuration, then submit a new request.</p>{!queue.data.recent_jobs?.length ? <p>No recent jobs.</p> : queue.data.recent_jobs.map(j => <div key={j.job_id} className="border-t border-border py-3"><p className="break-all">{j.job_type} · {j.status} · {formatQueueTimestamp(j.created_at)}</p><p className="ui-meta break-all">{j.job_id}</p>{j.error && <p role="status" className="text-danger-700 break-words">{j.error}</p>}{j.finished_at && <p className="ui-meta">Finished {formatQueueTimestamp(j.finished_at)}</p>}{["pending", "running", "cancel_requested"].includes(j.status) && <p className="ui-meta">{j.status === "pending" ? "Waiting for an eligible worker. Check worker job-type filters if this remains queued." : j.status === "cancel_requested" ? "Cancellation requested; waiting for the worker to stop safely." : "Claimed by a worker. A running state alone does not prove progress; inspect the worker log before retrying."}</p>}{sourceRoute(j) && <Link className="text-brand-700 underline" href={sourceRoute(j)!}>Open source and review current evidence</Link>}</div>)}</Card>
          </>
        )}
      </div>
    </RoleGate>
  );
}
