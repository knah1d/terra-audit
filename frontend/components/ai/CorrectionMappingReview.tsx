"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

type Correction = { id: string; item_label: string; change_summary: string; correction_document_id: string; correction_page: number; correction_end_page: number; target_document_id: string; target_section: string; target_equations: string; status: string; confirmation_stale: boolean };
export function CorrectionMappingReview() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["methodology-corrections"], queryFn: () => apiFetch<Correction[]>("/methodology/corrections") });
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const confirm = useMutation({ mutationFn: (id: string) => apiFetch(`/methodology/corrections/${encodeURIComponent(id)}/confirm`, { method: "POST" }), onSuccess: async () => {
    setChecked({}); await client.invalidateQueries({ queryKey: ["methodology-corrections"] }); await client.invalidateQueries({ queryKey: ["methodology-library-coverage"] });
  } });
  return <details className="mt-5 border-t border-border pt-4"><summary className="cursor-pointer ui-label">Review correction mappings</summary><p className="ui-secondary mt-3">These are curated mappings, not verbatim methodology quotes. Read the correction PDF and its target before confirming. Confirmation records this organization’s mapping review; it never approves readiness or issuance.</p>
    {query.isLoading && <p className="mt-3">Loading correction mappings…</p>}{(query.error || confirm.error) && <p role="alert" className="mt-3 text-danger-700">{query.error?.message || confirm.error?.message}</p>}
    {query.data?.map(row => <div key={row.id} className="mt-4 border-t border-border pt-3 space-y-2"><div className="flex flex-wrap gap-2 items-center"><Badge tone={row.status === "confirmed" ? "success" : "warning"}>{row.status === "confirmed" ? "Confirmed mapping" : "Unconfirmed mapping"}</Badge><h3 className="ui-label">{row.item_label}</h3></div>{row.confirmation_stale && <p className="text-warning-700 text-sm">A source or mapping changed; the previous confirmation is stale.</p>}<p className="text-sm">{row.change_summary}</p>{!row.target_section && !row.target_equations && <p className="text-warning-700 text-sm">The target has not been established. Curate the mapping before confirmation; no section is inferred automatically.</p>}<p className="ui-meta">Target: {row.target_document_id} · {row.target_section || "Section not established"}{row.target_equations ? ` · Equations ${row.target_equations}` : ""}</p><div className="flex flex-wrap gap-3"><a className="text-brand-700 underline text-sm" href={`/api/proxy/methodology/documents/${encodeURIComponent(row.correction_document_id)}/file#page=${row.correction_page}`} target="_blank" rel="noopener noreferrer">Open correction, page {row.correction_page}</a><a className="text-brand-700 underline text-sm" href={`/api/proxy/methodology/documents/${encodeURIComponent(row.target_document_id)}/file`} target="_blank" rel="noopener noreferrer">Open target document</a></div>{row.status !== "confirmed" && <><label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={!!checked[row.id]} disabled={confirm.isPending} onChange={e => setChecked(values => ({ ...values, [row.id]: e.target.checked }))} /><span>I checked this mapping against both documents.</span></label><Button size="sm" variant="secondary" disabled={!checked[row.id] || confirm.isPending || (!row.target_section && !row.target_equations)} onClick={() => confirm.mutate(row.id)}>Confirm this mapping</Button></>}</div>)}
  </details>;
}
