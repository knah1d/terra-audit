"use client";

import { Bell, ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { ProjectReviewQueue, SubmissionRow } from "@/components/reviews/ReviewQueue";
import { useProjects } from "@/hooks/use-projects";
import {
  useMarkNotificationRead, useMyReviews, useNotifications,
} from "@/hooks/use-reviews";

export default function ReviewsPage() {
  const projects = useProjects();
  const router = useRouter();
  const search = useSearchParams();
  const requestedProject = search.get("project") ?? "";
  // Defaults to the first project so the queue is never hidden behind an empty picker.
  const projectId = projects.data?.some(p => p.project_id === requestedProject) ? requestedProject : projects.data?.[0]?.project_id ?? "";
  function setProjectId(value: string) {
    const params = new URLSearchParams(search.toString());
    if (value) params.set("project", value); else params.delete("project");
    router.replace(`/reviews${params.size ? `?${params}` : ""}`, { scroll: false });
  }
  const myReviews = useMyReviews();
  const notifications = useNotifications();
  const markRead = useMarkNotificationRead();

  return (
    <div className="ui-container space-y-6">
      <PageHeader title="Reviews" subtitle="Internal review only — this is not external verification or registry issuance." />

      <Card>
        <div className="flex items-center gap-2 mb-3"><Bell className="size-4" /><h3 className="ui-subsection-title">Notifications</h3></div>
        {notifications.isLoading ? <Skeleton className="h-16" /> : !notifications.data?.length ? (
          <p className="ui-secondary">No notifications.</p>
        ) : (
          <div className="space-y-1">
            {notifications.data.slice(0, 8).map((n) => (
              <div key={n.id} className={`flex flex-wrap items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-sm ${!n.read_at ? "bg-brand-50/50" : ""}`}>
                <span>
                  {n.message}{" "}
                  {n.submission_id ? <Link href={`/reviews/${n.submission_id}`} className="underline">View review</Link> : n.recovery_route && <Link href={n.recovery_route} className="underline">{n.recovery_label ?? "Open source"}</Link>}
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
        <h3 className="ui-subsection-title mb-3">My reviews</h3>
        {myReviews.isLoading ? <Skeleton className="h-24" /> : !myReviews.data?.length ? (
          <EmptyState icon={ClipboardCheck} title="Nothing waiting for you" description="Submissions assigned to you that still need your review appear here." />
        ) : (
          <div>{myReviews.data.map((row) => <SubmissionRow key={row.submission_id} row={row} showProject />)}</div>
        )}
      </Card>

      <Card>
        <h3 className="ui-subsection-title mb-3">Project review queue</h3>
        <Select value={projectId} onChange={(e) => setProjectId(e.target.value)} aria-label="Project" className="mb-3 max-w-xs">
          {(projects.data ?? []).map((p) => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
        </Select>
        {!projectId ? (projects.isLoading ? <Skeleton className="h-24" /> :
          <p className="ui-secondary">Create a project to see its submissions.</p>
        ) : <ProjectReviewQueue projectId={projectId} />}
      </Card>
    </div>
  );
}
