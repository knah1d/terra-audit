"use client";

import { Bell, ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useProjects } from "@/hooks/use-projects";
import {
  useMarkNotificationRead, useMyReviews, useNotifications, useProjectSubmissions,
} from "@/hooks/use-reviews";
import type { ReviewSubmissionOut, SubmissionStatus } from "@/types/api";

const STATUS_TONE: Record<SubmissionStatus, "brand" | "success" | "warning" | "neutral" | "danger"> = {
  submitted: "brand", in_review: "brand", changes_requested: "warning",
  internally_approved: "success", rejected: "danger", withdrawn: "neutral",
};

function SubmissionRow({ row }: { row: ReviewSubmissionOut }) {
  const overdue = !!row.overdue;
  return (
    <Link href={`/reviews/${row.submission_id}`} className="flex flex-wrap items-center justify-between gap-2 border-t border-border py-3 text-sm first:border-t-0 focus-visible:outline-2 focus-visible:outline-brand-600">
      <div className="flex items-center gap-2">
        <Badge tone={STATUS_TONE[row.status]}>{row.status.replace(/_/g, " ")}</Badge>
        {overdue && <Badge tone="danger">overdue</Badge>}
        <span className="font-mono text-xs text-text-tertiary">{row.field_id}</span>
      </div>
      <span className="text-text-secondary">Submitted {new Date(row.submitted_at).toLocaleDateString()}</span>
    </Link>
  );
}

export default function ReviewsPage() {
  const projects = useProjects();
  const [projectId, setProjectId] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const myReviews = useMyReviews();
  const queue = useProjectSubmissions(projectId, { status: statusFilter || undefined });
  const notifications = useNotifications();
  const markRead = useMarkNotificationRead();

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader title="Reviews" subtitle="Internal review only — this is not external verification or registry issuance." />

      <Card>
        <div className="flex items-center gap-2 mb-3"><Bell className="size-4" /><h3 className="font-medium">Notifications</h3></div>
        {notifications.isLoading ? <Skeleton className="h-16" /> : !notifications.data?.length ? (
          <p className="text-sm text-text-secondary">No notifications.</p>
        ) : (
          <div className="space-y-1">
            {notifications.data.slice(0, 8).map((n) => (
              <div key={n.id} className={`flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-sm ${!n.read_at ? "bg-brand-50/50" : ""}`}>
                <span>
                  {n.message}{" "}
                  {n.submission_id && <Link href={`/reviews/${n.submission_id}`} className="underline">View</Link>}
                </span>
                {!n.read_at && (
                  <Button variant="ghost" size="sm" onClick={() => markRead.mutate(n.id)}>Mark read</Button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h3 className="mb-3 font-medium">My reviews</h3>
        {myReviews.isLoading ? <Skeleton className="h-24" /> : !myReviews.data?.length ? (
          <EmptyState icon={ClipboardCheck} title="Nothing assigned to you" description="Submissions assigned to you for review will appear here." />
        ) : (
          <div>{myReviews.data.map((row) => <SubmissionRow key={row.submission_id} row={row} />)}</div>
        )}
      </Card>

      <Card>
        <h3 className="mb-3 font-medium">Project review queue</h3>
        <div className="mb-3 flex flex-wrap gap-3">
          <Select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="max-w-xs">
            <option value="">Select a project…</option>
            {(projects.data ?? []).map((p) => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
          </Select>
          {projectId && (
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="max-w-xs">
              <option value="">All statuses</option>
              {["submitted", "in_review", "changes_requested", "internally_approved", "rejected", "withdrawn"].map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
              ))}
            </Select>
          )}
        </div>
        {!projectId ? (
          <p className="text-sm text-text-secondary">Select a project to see its submissions.</p>
        ) : queue.isLoading ? <Skeleton className="h-24" /> : queue.error ? (
          <Alert tone="danger" title="Could not load submissions">{queue.error.message}</Alert>
        ) : !queue.data?.length ? (
          <EmptyState icon={ClipboardCheck} title="No submissions" description="No calculations have been submitted for review in this project yet." />
        ) : (
          <div>{queue.data.map((row) => <SubmissionRow key={row.submission_id} row={row} />)}</div>
        )}
      </Card>
    </div>
  );
}
