"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { useAiExplain } from "@/hooks/use-ai-explain";

export function ExplainButton({ projectId, request, children }: {
  projectId: string; request: Record<string, unknown>; children: React.ReactNode;
}) {
  const ai = useAiExplain(projectId);
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);
  return <>
    <Button variant="secondary" size="sm" onClick={() => { setOpen(true); void ai.request(request); }}>{children}</Button>
    <dialog ref={dialog} onCancel={() => setOpen(false)} className="fixed m-auto max-h-[85vh] w-[min(720px,95vw)] overflow-y-auto rounded-xl border border-border bg-background p-6 text-text-primary backdrop:bg-black/60">
      <div className="flex items-start justify-between gap-4">
        <h2 className="ui-section-title">AI explanation — draft, not an official readiness decision</h2>
        <Button variant="secondary" size="sm" onClick={() => setOpen(false)}>Close</Button>
      </div>
      {ai.loading && <p role="status" className="my-4">Generating explanation… Hosted models may take longer on a cold start.</p>}
      {ai.error && <p role="alert" className="my-4 text-danger-700">{ai.error}</p>}
      {ai.explanation && <div className="space-y-4 py-4">
        {ai.explanation.deterministic_message && <p>{ai.explanation.deterministic_message}</p>}
        {ai.explanation.summary_claims.map((claim, i) => <div key={i}>
          <p>{claim.text}</p>
          <div className="flex flex-wrap gap-2 pt-2">{claim.sentence_ids.map(id => {
            const citation = ai.explanation!.citations_resolved.find(c => c.sentence_id === id);
            if (!citation) return null;
            const href = citation.document_id && citation.page ? `/api/proxy/methodology/documents/${encodeURIComponent(citation.document_id)}/file#page=${citation.page}` : citation.route;
            return href ? <a key={id} href={href} target={citation.document_id ? "_blank" : undefined} rel="noopener noreferrer" className="rounded border border-border px-2 py-1 text-xs" title={citation.text}>{citation.title || id}{citation.label ? ` · ${citation.label}` : ""}</a> : <span key={id} title={citation.text} className="rounded border border-border px-2 py-1 text-xs">{citation.title || id}{citation.label ? ` · ${citation.label}` : ""}</span>;
          })}</div>
        </div>)}
        {ai.explanation.missing_evidence.length > 0 && <section><h3 className="ui-subsection-title">Missing evidence</h3>{ai.explanation.missing_evidence.map((item, i) => <p key={i} className="py-2">{item.explanation} {item.route && <a className="text-brand-600 underline" href={item.route}>Go fix</a>}</p>)}</section>}
        {ai.explanation.conflicts.length > 0 && <section><h3 className="ui-subsection-title">Conflicts</h3>{ai.explanation.conflicts.map((item, i) => <p key={i}>{item.description}</p>)}</section>}
        {ai.explanation.limitations.map((item, i) => <p key={i} className="text-sm text-text-secondary">{item}</p>)}
        <p className="break-all text-xs text-text-tertiary">Provider: {ai.explanation.provider.provider} · Model: {ai.explanation.provider.model || "none"} · Context: {ai.explanation.context_sha256}</p>
      </div>}
    </dialog>
  </>;
}
