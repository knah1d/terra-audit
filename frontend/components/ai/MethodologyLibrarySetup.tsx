"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { MethodologySourceStatus } from "@/hooks/use-methodology";
import { CorrectionMappingReview } from "./CorrectionMappingReview";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

type LibraryDocument = MethodologySourceStatus;
type IngestionJob = { job_id: string; status: string; error: string | null; result?: {
  outcome: string; attention_count: number; documents: { document_id: string; status: string; error?: string; chunks?: number }[];
} | null };

export function MethodologyLibrarySetup() {
  const client = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const library = useQuery({
    queryKey: ["methodology-library-status"],
    queryFn: () => apiFetch<LibraryDocument[]>("/methodology/library/status"),
  });
  const job = useQuery({
    queryKey: ["methodology-ingestion-job", jobId],
    queryFn: () => apiFetch<IngestionJob>(`/methodology/library/ingest/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: query => query.state.data && ["done", "error", "cancelled"].includes(query.state.data.status) ? false : 3000,
  });
  useEffect(() => {
    if (job.data?.status === "done") {
      void client.invalidateQueries({ queryKey: ["methodology-library-status"] });
      void client.invalidateQueries({ queryKey: ["methodology-library-coverage"] });
    }
  }, [job.data?.status, client]);
  const pending = !!jobId && !job.error && (!job.data || ["pending", "running"].includes(job.data.status));
  const ingest = useMutation({
    mutationFn: () => apiFetch<{ job_id: string }>("/methodology/library/ingest", { method: "POST" }),
    onSuccess: result => { setJobId(result.job_id); void client.invalidateQueries({ queryKey: ["methodology-library-status"] }); },
  });

  return <Card>
    <h2 className="ui-section-title">AI methodology library</h2>
    <p className="mt-3 text-sm text-text-secondary">Index the registered PDFs so draft explanations can cite methodology pages. External references have no local PDF to index.</p>
    <div className="mt-4 flex flex-wrap gap-3">
      <Button loading={ingest.isPending} disabled={pending || library.isLoading || !!library.error} onClick={() => ingest.mutate()}>Index methodology PDFs</Button>
      <Button variant="secondary" loading={library.isFetching} onClick={() => void library.refetch()}>Refresh index status</Button>
      <Link className="self-center text-sm text-brand-700" href="/admin/queue">View worker &amp; queue</Link>
    </div>
    {library.isLoading && <p className="mt-3 text-sm">Loading library status…</p>}
    {[library.error, ingest.error, job.error].filter(Boolean).map((error, i) => <p className="mt-3 text-sm" role="alert" key={i}>{error?.message}</p>)}
    {jobId && <p className="mt-3 text-sm" role="status">Indexing job: {job.data?.status ?? "checking status"}. {job.data?.status === "done" ? "Document counts refresh automatically. Check per-document results below; a finished job can still have missing or failed documents." : ""}</p>}
    {job.data?.error && <p className="mt-3 text-sm" role="alert">{job.data.error}</p>}
    {pending && <p className="mt-2 text-sm text-text-secondary">A worker must accept methodology_ingest jobs. An AI-only worker will leave this job queued. Run the worker with <code>python -m backend.worker --job-types ai_explain methodology_ingest</code>. The worker needs the registered PDFs and pdftotext. After completion, request a new explanation to use the indexed sources.</p>}
    {job.data?.result && <div className="mt-4 rounded-lg border border-border p-3"><h3 className="ui-subsection-title">Last indexing results</h3><p className="ui-secondary mt-2">{job.data.result.attention_count} document(s) need attention.</p>{job.data.result.documents.map(doc => <p className="mt-2 text-sm break-words" key={doc.document_id}>{doc.document_id}: {doc.status.replaceAll("_", " ")}{doc.error ? ` — ${doc.error}` : ""}</p>)}</div>}
    <p className="ui-meta mt-4">A current index is required for methodology citations. Missing files must be restored on the host; external references need a registered local PDF. Re-index stale sources. Scanned PDFs with no text require a separate OCR decision.</p>
    <div className="mt-4 space-y-3">
      {library.data?.map(document => <div key={document.document_id} className="border-t border-border pt-3 text-sm">
        <strong>{document.title}</strong>
        <p className="text-text-secondary">{document.status.replaceAll("_", " ")} · {document.chunks} chunks · {document.pages} pages</p>
      </div>)}
    </div>
    <CorrectionMappingReview />
  </Card>;
}
