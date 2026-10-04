"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "@/app/providers";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Field";
import { useCropSeasons } from "@/hooks/use-crop-seasons";
import { apiFetch, apiFetchBlob } from "@/lib/api";
import { formatQueueTimestamp } from "@/lib/format";

type Attachment = { attachment_id: string; filename: string; size_bytes: number; uploaded_at: string | null };
export default function EvidenceFilesPage() {
  const field = useFieldContext();
  const params = useSearchParams();
  return <EvidenceFilesView key={`${field.field_id}:${params.toString()}`} />;
}

function EvidenceFilesView() {
  const field = useFieldContext();
  const session = useSession();
  const queryClient = useQueryClient();
  const params = useSearchParams();
  const [season, setSeason] = useState(params.get("season") ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const seasons = useCropSeasons(field.field_id);
  const validTarget = !season || !!seasons.data?.some(s => s.id === season);
  const targetType = season ? "season" : "field";
  const targetId = season || field.field_id;
  const files = useQuery({ queryKey: ["attachments", targetType, targetId], queryFn: () => apiFetch<Attachment[]>(`/attachments?target_type=${targetType}&target_id=${encodeURIComponent(targetId)}`), enabled: validTarget });
  const writable = session?.role === "admin" || session?.role === "analyst";
  async function download(file: Attachment) {
    setError("");
    try {
      const blob = await apiFetchBlob(`/attachments/${file.attachment_id}/download`);
      const url = URL.createObjectURL(blob); const link = document.createElement("a");
      link.href = url; link.download = file.filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(e instanceof Error ? e.message : "Download failed"); }
  }
  return <div className="ui-container space-y-6">
    <Card><h2 className="ui-section-title mb-3">Evidence files</h2><p className="ui-secondary mb-4">Upload original documents and photographs. Uploading a file does not confirm its contents or satisfy readiness automatically.</p>
      <label className="ui-label">Attach to<Select value={season} onChange={e => { setSeason(e.target.value); setNotice(""); }} disabled={busy || seasons.isLoading}>
        <option value="">This field</option>{seasons.data?.map(s => <option key={s.id} value={s.id}>{s.payload.name}</option>)}
      </Select></label>
      {!validTarget && !seasons.isLoading && <p role="alert">That season is not available on this field. Choose another target.</p>}
      {writable && <form className="mt-4 space-y-3" onSubmit={async e => {
        e.preventDefault(); const form = e.currentTarget; const data = new FormData(form);
        data.set("field_id", field.field_id); data.set("target_type", targetType); data.set("target_id", targetId);
        setBusy(true); setError(""); setNotice("");
        try { await apiFetch("/attachments", { method: "POST", form: data }); form.reset(); setNotice("Evidence uploaded. Review its contents before using it."); await queryClient.invalidateQueries({ queryKey: ["attachments"] }); await queryClient.invalidateQueries({ queryKey: ["ai-workspace"] }); }
        catch (e) { setError(e instanceof Error ? e.message : "Upload failed"); }
        finally { setBusy(false); }
      }}><label className="ui-label">Original file<input className="ui-control block w-full" type="file" name="file" required disabled={busy} accept=".pdf,.docx,.txt,.csv,.jpg,.jpeg,.png,.webp" /></label><p className="ui-meta">PDF, DOCX, text, CSV, JPEG, PNG and WebP. The server enforces its configured upload limit.</p><Button type="submit" loading={busy} disabled={!validTarget || seasons.isLoading}>Upload evidence</Button></form>}
    </Card>
    {(error || files.error || seasons.error) && <p role="alert" className="text-danger-700">{error || files.error?.message || seasons.error?.message}</p>}
    {notice && <p role="status" className="text-success-700">{notice}</p>}
    <Card><h3 className="ui-subsection-title mb-3">Files for this target</h3>{files.isLoading ? <p>Loading files…</p> : !files.error && validTarget && !files.data?.length ? <p>No evidence files uploaded yet.</p> : files.data?.map(file => <div key={file.attachment_id} className="flex flex-wrap items-center justify-between gap-3 border-t border-border py-3"><div className="min-w-0"><p className="break-words">{file.filename}</p><p className="ui-meta">{(file.size_bytes / 1024).toFixed(1)} KB · {formatQueueTimestamp(file.uploaded_at)}</p></div><Button variant="secondary" onClick={() => void download(file)}>Download</Button></div>)}</Card>
  </div>;
}
