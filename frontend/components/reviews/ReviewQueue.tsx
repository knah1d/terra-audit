"use client";

import { ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { useProjectSubmissions } from "@/hooks/use-reviews";
import { formatDate } from "@/lib/format";
import type { ReviewSubmissionOut, SubmissionStatus } from "@/types/api";

const STATUS_TONE: Record<SubmissionStatus, "brand" | "success" | "warning" | "neutral" | "danger"> = {
  submitted: "brand", in_review: "brand", changes_requested: "warning",
  internally_approved: "success", rejected: "danger", withdrawn: "neutral",
};

export function SubmissionRow({ row, showProject = false }: { row: ReviewSubmissionOut; showProject?: boolean }) {
  return (
    <Link href={`/reviews/${row.submission_id}`} className="flex flex-wrap items-center justify-between gap-2 border-t border-border py-3 text-sm first:border-t-0 hover:bg-surface-muted/40">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <Badge tone={STATUS_TONE[row.status]}>{row.status.replace(/_/g, " ")}</Badge>
        {row.overdue && <Badge tone="danger">overdue</Badge>}
        <span className="font-medium">{row.field_name ?? "Field"}</span>
        {showProject && row.project_name && <span className="text-text-secondary">· {row.project_name}</span>}
      </div>
      <span className="text-text-secondary">
        {row.reviewer_email ? `Reviewer: ${row.reviewer_email}` : <span className="text-warning-700">No reviewer yet</span>}
        {" · "}Submitted {formatDate(row.submitted_at)}
      </span>
    </Link>
  );
}

/** One project's submissions, filterable by status (or "needs a reviewer"). */
export function ProjectReviewQueue({ projectId }: { projectId: string }) {
  const [filter, setFilter] = useState("open");
  const status = filter === "open" || filter === "unassigned" ? "submitted,in_review" : filter || undefined;
  const queue = useProjectSubmissions(projectId, { status });
  const rows = (queue.data ?? []).filter((r) => filter !== "unassigned" || !r.assigned_reviewer_id);

  return (
    <div className="space-y-3">
      <Select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Show" className="max-w-xs">
        <option value="open">Open (submitted or in review)</option>
        <option value="unassigned">Needs a reviewer</option>
        <option value="changes_requested">Changes requested</option>
        <option value="internally_approved">Approved</option>
        <option value="rejected">Rejected</option>
        <option value="withdrawn">Withdrawn</option>
        <option value="">All</option>
      </Select>
      {queue.isLoading ? <Skeleton className="h-24" /> : queue.error ? (
        <Alert tone="danger" title="Could not load submissions">{queue.error.message}</Alert>
      ) : !rows.length ? (
        <EmptyState icon={ClipboardCheck} title="Nothing here" description="Submit a saved calculation from a field's Calculations tab to start a review." />
      ) : (
        <div>{rows.map((row) => <SubmissionRow key={row.submission_id} row={row} />)}</div>
      )}
    </div>
  );
}
