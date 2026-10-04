"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

type LibraryDocument = {
  document_id: string; title: string; chunks: number; pages: number;
  status: "indexed" | "not_indexed" | "stale" | "external_reference";
};
type IngestionJob = { job_id: string; status: string; error: string | null };

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
    {jobId && <p className="mt-3 text-sm" role="status">Indexing job: {job.data?.status ?? "checking status"}. {job.data?.status === "done" ? "Refresh index status to see the updated document counts." : ""}</p>}
    {job.data?.error && <p className="mt-3 text-sm" role="alert">{job.data.error}</p>}
    {pending && <p className="mt-2 text-sm text-text-secondary">A worker must accept methodology_ingest jobs. An AI-only worker will leave this job queued. After completion, request a new explanation to use the indexed sources.</p>}
    <div className="mt-4 space-y-3">
      {library.data?.map(document => <div key={document.document_id} className="border-t border-border pt-3 text-sm">
        <strong>{document.title}</strong>
        <p className="text-text-secondary">{document.status.replaceAll("_", " ")} · {document.chunks} chunks · {document.pages} pages</p>
      </div>)}
    </div>
  </Card>;
}
