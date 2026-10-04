"use client";
import Link from "next/link";

import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { RoleGate } from "@/components/ui/RoleGate";
import { Skeleton } from "@/components/ui/Skeleton";
import { useQueueStatus } from "@/hooks/use-monitoring-ops";
import { formatQueueTimestamp } from "@/lib/format";

export default function QueueStatusPage() {
  const queue = useQueueStatus();
  return (
    <RoleGate allow={["admin"]} fallback={<Alert tone="danger" title="Admins only">You don&apos;t have access to this page.</Alert>}>
      <div className="ui-container space-y-6">
        <PageHeader title="Worker & queue status" subtitle="Operational visibility into the durable job queue — not tenant data." />
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
              <h3 className="ui-subsection-title mb-2">Workers</h3>
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
            <Card><h3 className="ui-subsection-title mb-3">Recent jobs in your organization</h3><p className="ui-meta mb-3">Failed jobs keep their error. Return to the source, check current evidence and configuration, then submit a new request.</p>{!queue.data.recent_jobs?.length ? <p>No recent jobs.</p> : queue.data.recent_jobs.map(j => <div key={j.job_id} className="border-t border-border py-3"><p className="break-all">{j.job_type} · {j.status} · {formatQueueTimestamp(j.created_at)}</p><p className="ui-meta break-all">{j.job_id}</p>{j.error && <p role="status" className="text-danger-700 break-words">{j.error}</p>}{j.field_id ? <Link className="text-brand-700 underline" href={`/fields/${encodeURIComponent(j.field_id)}/${j.job_type === "ai_explain" ? "calculations" : "signal-analytics"}${j.project_id ? `?project=${encodeURIComponent(j.project_id)}` : ""}`}>Open source field</Link> : j.project_id && <Link className="text-brand-700 underline" href={`/projects/${encodeURIComponent(j.project_id)}/ai`}>Open AI workspace</Link>}</div>)}</Card>
          </>
        )}
      </div>
    </RoleGate>
  );
}
