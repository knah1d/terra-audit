"use client";

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
              <p className="ui-meta mb-2">Times are shown in your browser&apos;s local timezone.</p>
              {!queue.data.workers.length ? <p className="ui-secondary">No workers have registered yet — start one with `python -m backend.worker`.</p> : (
                <div className="space-y-1 text-sm">
                  {queue.data.workers.map((w) => (
                    <p key={w.worker_id}>
                      <Badge tone={w.stopped_at ? "neutral" : "success"}>{w.stopped_at ? "stopped" : "alive"}</Badge>{" "}
                      {w.hostname} · last heartbeat {formatQueueTimestamp(w.last_heartbeat_at)}
                    </p>
                  ))}
                </div>
              )}
            </Card>
          </>
        )}
      </div>
    </RoleGate>
  );
}
