"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput, TextArea } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useTeamUsers } from "@/hooks/use-team";
import { useAddProjectMember, useProjectMembers } from "@/hooks/use-projects";
import {
  useAddComment, useAssignReviewer, useCloseFinding, useCreateFinding, useFindingComments,
  useSubmissionDetail, useSubmissionDiff, useTransitionSubmission,
} from "@/hooks/use-reviews";
import type { FindingOut, ReadinessCheck, SubmissionStatus } from "@/types/api";

const STATUS_TONE: Record<SubmissionStatus, "brand" | "success" | "warning" | "neutral" | "danger"> = {
  submitted: "brand", in_review: "brand", changes_requested: "warning",
  internally_approved: "success", rejected: "danger", withdrawn: "neutral",
};

const NEXT_STATUSES: Record<SubmissionStatus, { value: string; label: string; reasonRequired: boolean }[]> = {
  submitted: [{ value: "in_review", label: "Start review", reasonRequired: false },
              { value: "withdrawn", label: "Withdraw", reasonRequired: true }],
  in_review: [
    { value: "changes_requested", label: "Request changes", reasonRequired: true },
    { value: "internally_approved", label: "Internally approve", reasonRequired: true },
    { value: "rejected", label: "Reject", reasonRequired: true },
    { value: "withdrawn", label: "Withdraw", reasonRequired: true },
  ],
  changes_requested: [{ value: "withdrawn", label: "Withdraw", reasonRequired: true }],
  internally_approved: [], rejected: [], withdrawn: [],
};

const SEVERITY_TONE: Record<string, "danger" | "warning" | "neutral"> = {
  blocking: "danger", major: "warning", minor: "neutral", info: "neutral",
};

const READINESS_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  satisfied: "success", not_applicable: "neutral", unsupported: "neutral",
  missing: "danger", needs_review: "warning",
};

function ReadinessList({ checklist }: { checklist: ReadinessCheck[] }) {
  return (
    <div className="space-y-2">
      {checklist.map((c) => (
        <div key={c.requirement_id} className="flex flex-wrap items-start gap-2 border-t border-border py-2 text-sm first:border-t-0 first:pt-0">
          <Badge tone={READINESS_TONE[c.status]}>{c.status.replace("_", " ")}</Badge>
          <div className="min-w-0 flex-1">
            <p className="font-mono text-xs text-text-tertiary">{c.requirement_id}</p>
            <p>{c.explanation}</p>
            {c.source_reference && <p className="text-xs text-text-tertiary">{c.source_reference}</p>}
            {c.required_evidence && <p className="text-xs text-text-tertiary">Required evidence: {c.required_evidence}</p>}
            {c.implementation_support && c.implementation_support !== "implemented" && (
              <p className="text-xs text-warning-700">Implementation: {c.implementation_support === "unsupported" ? "not implemented by this system" : "partially implemented"}</p>
            )}
            {c.decided_by && <p className="text-xs text-text-secondary">Recorded decision: {c.reason}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

function FindingCard({ finding, submissionId }: { finding: FindingOut; submissionId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [closeReason, setCloseReason] = useState("");
  const [commentBody, setCommentBody] = useState("");
  const [proposed, setProposed] = useState(false);
  const comments = useFindingComments(expanded ? finding.finding_id : null);
  const close = useCloseFinding(submissionId);
  const addComment = useAddComment(finding.finding_id, submissionId);
  const [error, setError] = useState("");

  return (
    <div className="border-t border-border py-3 text-sm first:border-t-0">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={SEVERITY_TONE[finding.severity]}>{finding.severity}</Badge>
        <Badge tone={finding.status === "open" ? "warning" : "success"}>{finding.status}</Badge>
        {finding.requirement_id && <span className="font-mono text-xs text-text-tertiary">{finding.requirement_id}</span>}
        {finding.carried_from_finding_id && <Badge tone="neutral">carried forward</Badge>}
      </div>
      <p className="mt-1">{finding.description}</p>
      {finding.requested_action && <p className="text-text-secondary">Requested: {finding.requested_action}</p>}
      {finding.status === "closed" && <p className="text-text-secondary">Closed: {finding.close_reason}</p>}
      {error && <p role="alert" className="text-danger-700">{error}</p>}
      <button className="mt-1 text-xs underline" onClick={() => setExpanded((v) => !v)}>
        {expanded ? "Hide discussion" : "Show discussion"}
      </button>
      {expanded && (
        <div className="mt-2 space-y-2 rounded-lg bg-surface-muted/40 p-2">
          {(comments.data ?? []).map((cm) => (
            <p key={cm.id} className="text-sm">{cm.is_proposed_resolution && <Badge tone="brand">proposed resolution</Badge>} {cm.body}</p>
          ))}
          <form className="flex gap-2" onSubmit={(e) => {
            e.preventDefault();
            setError("");
            addComment.mutateAsync({ body: commentBody, is_proposed_resolution: proposed })
              .then(() => setCommentBody(""))
              .catch((err) => setError(err instanceof Error ? err.message : "Failed to add comment"));
          }}>
            <TextInput value={commentBody} onChange={(e) => setCommentBody(e.target.value)} placeholder="Reply…" required className="flex-1" />
            <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={proposed} onChange={(e) => setProposed(e.target.checked)} />Proposed resolution</label>
            <Button type="submit" size="sm" loading={addComment.isPending}>Reply</Button>
          </form>
          {finding.status === "open" && (
            <form className="flex gap-2" onSubmit={(e) => {
              e.preventDefault();
              setError("");
              close.mutateAsync({ findingId: finding.finding_id, reason: closeReason })
                .then(() => setCloseReason(""))
                .catch((err) => setError(err instanceof Error ? err.message : "Failed to close finding"));
            }}>
              <TextInput value={closeReason} onChange={(e) => setCloseReason(e.target.value)} placeholder="Reason for closing (reviewer only)" required className="flex-1" />
              <Button type="submit" variant="secondary" size="sm" loading={close.isPending}>Close finding</Button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}

export default function SubmissionDetailPage() {
  const { submissionId } = useParams<{ submissionId: string }>();
  const detail = useSubmissionDetail(submissionId);
  const team = useTeamUsers();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  const [assignReason, setAssignReason] = useState("");
  const [newMemberId, setNewMemberId] = useState("");
  const [newMemberReason, setNewMemberReason] = useState("");
  const [toStatus, setToStatus] = useState("");
  const [reason, setReason] = useState("");
  const [findingSeverity, setFindingSeverity] = useState("major");
  const [findingDescription, setFindingDescription] = useState("");
  const [findingAction, setFindingAction] = useState("");
  const [showDiff, setShowDiff] = useState(false);

  const submission = detail.data?.submission;
  const projectMembers = useProjectMembers(submission?.project_id);
  const addMember = useAddProjectMember(submission?.project_id);
  const assign = useAssignReviewer(submissionId, submission?.project_id);
  const transitionMutation = useTransitionSubmission(submissionId, submission?.project_id);
  const createFinding = useCreateFinding(submissionId);
  const diff = useSubmissionDiff(submissionId, !!submission?.previous_submission_id);

  if (detail.isLoading) return <Skeleton className="h-96" />;
  if (detail.error) return <Alert tone="danger" title="Could not load this submission">{detail.error.message}</Alert>;
  if (!detail.data || !submission) return null;

  const { calculation, findings, events, assignment_history } = detail.data;
  const options = NEXT_STATUSES[submission.status] ?? [];
  const openBlockers = findings.filter((f) => f.severity === "blocking" && f.status === "open");

  async function perform(action: () => Promise<void>) {
    setError(""); setNotice("");
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Action failed"); }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <PageHeader
        title={<span className="flex items-center gap-2">Submission <Badge tone={STATUS_TONE[submission.status]}>{submission.status.replace(/_/g, " ")}</Badge></span>}
        subtitle="Internal approval only. This never sets or implies external verification or registry issuance."
      />
      {error && <p role="alert" className="rounded-lg bg-danger-50 p-3 text-danger-700">{error}</p>}
      {notice && <p role="status" className="text-sm text-success-700">{notice}</p>}

      <Card>
        <h3 className="mb-2 font-medium">Calculation</h3>
        <p className="text-sm">Field <span className="font-mono">{calculation.field_id}</span> · {calculation.accounting_pathway} · v{calculation.version}</p>
        <p className="text-sm">Monitoring period {calculation.monitoring_period_start} to {calculation.monitoring_period_end}</p>
        <p className="text-sm font-mono">Final issuance: {calculation.final_issuance ?? "—"} tCO2e</p>
        <p className="text-xs text-text-tertiary">{calculation.methodology_version} · engine {calculation.engine_version}</p>
        {submission.previous_submission_id && (
          <Button variant="ghost" size="sm" className="mt-2" onClick={() => setShowDiff((v) => !v)}>
            {showDiff ? "Hide" : "Compare to previous version"}
          </Button>
        )}
        {showDiff && diff.data && (
          <div className="mt-2 rounded-lg bg-surface-muted/40 p-3 text-sm">
            <p className="font-medium">Inputs changed</p>
            {Object.entries(diff.data.inputs_changed).map(([k, v]) => (
              <p key={k}>{k}: {JSON.stringify(v.previous)} → {JSON.stringify(v.current)}</p>
            ))}
            <p className="mt-2 font-medium">Result changed</p>
            {Object.entries(diff.data.result_changed).map(([k, v]) => (
              <p key={k}>{k}: {JSON.stringify(v.previous)} → {JSON.stringify(v.current)}</p>
            ))}
            <p className="mt-2 font-medium">Readiness changed</p>
            {Object.entries(diff.data.readiness_changed).map(([k, v]) => (
              <p key={k}>{k}: {v.previous ?? "—"} → {v.current ?? "—"}</p>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h3 className="mb-2 font-medium">Frozen readiness checklist</h3>
        <p className="mb-2 text-xs text-text-tertiary">As recorded at commit time — not a certification of full methodology compliance.</p>
        <ReadinessList checklist={calculation.readiness} />
      </Card>

      <Card>
        <h3 className="mb-2 font-medium">Reviewer</h3>
        <p className="text-sm">Currently assigned: <span className="font-mono">{submission.assigned_reviewer_id ?? "unassigned"}</span></p>
        <p className="mt-1 text-xs text-text-tertiary">
          The picker below only lists current project members — assigning a reviewer never grants project
          access on its own. To assign someone new, add them as a project member first (below).
        </p>
        <form className="mt-3 flex flex-wrap gap-2" onSubmit={(e) => {
          e.preventDefault();
          void perform(async () => {
            await assign.mutateAsync({ reviewer_id: reviewerId || null, reason: assignReason });
            setAssignReason(""); setNotice("Reviewer assignment updated.");
          });
        }}>
          <Select value={reviewerId} onChange={(e) => setReviewerId(e.target.value)} className="max-w-xs">
            <option value="">Unassign</option>
            {(projectMembers.data ?? [])
              .filter((m) => m.user_id !== submission.submitted_by)
              .map((m) => <option key={m.user_id} value={m.user_id}>{m.email} ({m.project_role})</option>)}
          </Select>
          <TextInput value={assignReason} onChange={(e) => setAssignReason(e.target.value)} placeholder="Reason for this assignment" required className="flex-1" />
          <Button type="submit" variant="secondary" loading={assign.isPending}>Assign / reassign</Button>
        </form>

        <details className="mt-3">
          <summary className="cursor-pointer text-sm underline">Add a new project member</summary>
          <form className="mt-2 flex flex-wrap gap-2" onSubmit={(e) => {
            e.preventDefault();
            void perform(async () => {
              await addMember.mutateAsync({ user_id: newMemberId, project_role: "contributor", reason: newMemberReason });
              setNewMemberId(""); setNewMemberReason(""); setNotice("Project member added.");
            });
          }}>
            <Select value={newMemberId} onChange={(e) => setNewMemberId(e.target.value)} className="max-w-xs" required>
              <option value="">Choose a teammate…</option>
              {(team.data ?? [])
                .filter((u) => !(projectMembers.data ?? []).some((m) => m.user_id === u.user_id))
                .map((u) => <option key={u.user_id} value={u.user_id}>{u.email}</option>)}
            </Select>
            <TextInput value={newMemberReason} onChange={(e) => setNewMemberReason(e.target.value)} placeholder="Reason for adding them" className="flex-1" />
            <Button type="submit" variant="secondary" size="sm" loading={addMember.isPending}>Add as contributor</Button>
          </form>
        </details>
      </Card>

      {!!options.length && (
        <Card>
          <h3 className="mb-2 font-medium">Decision</h3>
          {!!openBlockers.length && (
            <Alert tone="warning" title="Blocking findings open">
              {openBlockers.length} blocking finding(s) must be closed before this can be internally approved.
            </Alert>
          )}
          <form className="mt-3 flex flex-wrap gap-2" onSubmit={(e) => {
            e.preventDefault();
            void perform(async () => {
              await transitionMutation.mutateAsync({ if_version: submission.version, to_status: toStatus, reason: reason || null });
              setReason(""); setToStatus(""); setNotice(`Submission moved to ${toStatus.replace(/_/g, " ")}.`);
            });
          }}>
            <Select value={toStatus} onChange={(e) => setToStatus(e.target.value)} required className="max-w-xs">
              <option value="">Choose an action…</option>
              {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </Select>
            <TextInput value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason / approval statement" className="flex-1" />
            <Button type="submit" loading={transitionMutation.isPending}>Confirm</Button>
          </form>
        </Card>
      )}

      <Card>
        <h3 className="mb-2 font-medium">Findings</h3>
        {!findings.length ? <p className="text-sm text-text-secondary">No findings recorded.</p> :
          findings.map((f) => <FindingCard key={f.finding_id} finding={f} submissionId={submissionId} />)}
        <form className="mt-3 grid gap-2 sm:grid-cols-2" onSubmit={(e) => {
          e.preventDefault();
          void perform(async () => {
            await createFinding.mutateAsync({
              severity: findingSeverity, description: findingDescription, requested_action: findingAction,
            });
            setFindingDescription(""); setFindingAction(""); setNotice("Finding recorded.");
          });
        }}>
          <Select value={findingSeverity} onChange={(e) => setFindingSeverity(e.target.value)}>
            <option value="blocking">Blocking</option><option value="major">Major</option>
            <option value="minor">Minor</option><option value="info">Info</option>
          </Select>
          <div />
          <TextArea value={findingDescription} onChange={(e) => setFindingDescription(e.target.value)} placeholder="Description" required className="sm:col-span-2" />
          <TextInput value={findingAction} onChange={(e) => setFindingAction(e.target.value)} placeholder="Requested action (optional)" className="sm:col-span-2" />
          <div><Button type="submit" variant="secondary" loading={createFinding.isPending}>Add finding</Button></div>
        </form>
      </Card>

      <Card>
        <h3 className="mb-2 font-medium">Activity</h3>
        <div className="space-y-1 text-sm">
          {[...events.map((e) => ({ at: e.created_at, text: `${e.from_status || "—"} → ${e.to_status}${e.reason ? `: ${e.reason}` : ""}` })),
            ...assignment_history.map((a) => ({ at: a.created_at, text: `Reviewer set to ${a.reviewer_id ?? "unassigned"}: ${a.reason}` }))]
            .sort((a, b) => a.at.localeCompare(b.at))
            .map((item, i) => <p key={i} className="border-t border-border py-1.5 first:border-t-0">{new Date(item.at).toLocaleString()} — {item.text}</p>)}
        </div>
      </Card>
    </div>
  );
}
