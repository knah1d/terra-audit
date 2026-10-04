"use client";
import Link from "next/link";
import { useSession } from "@/app/providers";
import { useMethodologyCoverage } from "@/hooks/use-methodology";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

export function MethodologyCoverage({ projectId, pathway }: { projectId: string; pathway: string }) {
  const query = useMethodologyCoverage(projectId, pathway);
  const session = useSession();
  const data = query.data;
  return <section className="mt-4 border-t border-border pt-4" aria-label="Methodology source coverage">
    <div className="flex flex-wrap items-center justify-between gap-3"><h4 className="ui-subsection-title">AI source coverage</h4><Button size="sm" variant="secondary" loading={query.isFetching} onClick={() => void query.refetch()}>Refresh coverage</Button></div>
    {query.isLoading && <p className="ui-secondary mt-2">Checking source coverage…</p>}
    {query.error && <p role="alert" className="text-danger-700 mt-2">{query.error.message}</p>}
    {data && <div className="space-y-3 mt-3">
      <p className="ui-secondary">{data.counts.indexed ?? 0} of {data.documents.length} bundle documents have a current index. {data.all_sources_indexed ? "All bundle sources are indexed." : "Source coverage is incomplete; draft explanations may cite project records without the missing methodology text."}</p>
      {!data.all_sources_indexed && <p className="text-sm text-warning-700">{session?.role === "admin" ? <Link className="underline" href="/admin/setup">Open Product setup to index PDFs and inspect failures.</Link> : "Ask an organization administrator to index the missing methodology PDFs in Product setup."} Indexing does not change calculation results or readiness decisions.</p>}
      <p className={data.corrections.unconfirmed > 0 ? "text-sm text-warning-700" : "ui-meta"}>{data.corrections.total} correction mappings · {data.corrections.unconfirmed} unconfirmed. Indexing correction PDFs does not confirm their mappings.</p>
      {!!data.corrections.outside_bundle_document_ids.length && <p className="text-warning-700 text-sm">Linked corrections outside the resolved bundle: {data.corrections.outside_bundle_document_ids.join(", ")}. Their text is excluded from AI retrieval.</p>}
      <details open={!data.all_sources_indexed || data.corrections.unconfirmed > 0}><summary className="cursor-pointer ui-label">Documents in {data.bundle_version}</summary><div className="mt-3 space-y-3">{data.documents.map(doc => <div key={doc.document_id} className="border-t border-border pt-3"><div className="flex flex-wrap items-center gap-2"><Badge tone={doc.status === "indexed" ? "success" : "warning"}>{doc.status.replaceAll("_", " ")}</Badge><span className="text-sm">{doc.title}</span></div><p className="ui-meta mt-1">{doc.document_type.replaceAll("_", " ")} · {doc.chunks} text chunks · {doc.pages} pages</p>{doc.local_file_available && <a className="text-sm text-brand-700 underline" href={`/api/proxy/methodology/documents/${encodeURIComponent(doc.document_id)}/file`} target="_blank" rel="noopener noreferrer">Open source PDF</a>}</div>)}</div></details>
      <p className="ui-meta">{data.notice}</p>
    </div>}
  </section>;
}
