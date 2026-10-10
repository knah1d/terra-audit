"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, FileDown, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { apiFetch, apiFetchBlob } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { formatDate } from "@/lib/format";
import type { ProjectOut } from "@/types/api";

type ProjectDocument = {
  document_id: string; category: string; title: string; filename: string; content_type: string;
  size_bytes: number; sha256: string; uploaded_at: string; uploaded_by_email: string | null;
};
// What a verifier normally expects alongside the monitoring report.
const EXPECTED = ["pdd", "monitoring_plan", "additionality", "land_tenure", "leakage"];

/** Project-level documents for the verifier; they ship in the MRV evidence package. */
export function ProjectDocuments({ project }: { project: ProjectOut }) {
  const base = `/projects/${encodeURIComponent(project.project_id)}/documents`;
  const queryClient = useQueryClient();
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [category, setCategory] = useState("pdd");
  const [title, setTitle] = useState("");
  const docs = useQuery({
    queryKey: ["project-documents", project.project_id],
    queryFn: () => apiFetch<{ categories: Record<string, string>; documents: ProjectDocument[] }>(base),
  });
  const refresh = () => {
    for (const key of [["project-documents", project.project_id], ["project-mrv", project.project_id]]) {
      void queryClient.invalidateQueries({ queryKey: key });
    }
  };
  const upload = useMutation({
    mutationFn: (form: FormData) => apiFetch<ProjectDocument>(base, { method: "POST", form }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiFetch(`${base}/${encodeURIComponent(id)}`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  const categories = docs.data?.categories ?? {};
  const documents = docs.data?.documents ?? [];

  return (
    <Card className="space-y-4">
      <div>
        <h3 className="ui-subsection-title">Project documents</h3>
        <p className="ui-secondary">Documents for the verifier. They are listed in the report and included in the evidence package.</p>
      </div>
      {docs.isLoading ? <Skeleton className="h-24" /> : docs.error ? (
        <Alert tone="danger" title="Could not load project documents">{docs.error.message}</Alert>
      ) : <>
        <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
          {EXPECTED.map((c) => {
            const has = documents.some((d) => d.category === c);
            return (
              <li key={c} className="flex items-center gap-2">
                {has ? <CheckCircle2 className="size-4 text-success-700" /> : <Circle className="size-4 text-text-tertiary" />}
                <span className={has ? "" : "text-text-secondary"}>{categories[c] ?? c}</span>
              </li>
            );
          })}
        </ul>

        {!!documents.length && (
          <div className="divide-y divide-border-subtle rounded-lg border border-border">
            {documents.map((d) => (
              <div key={d.document_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
                <div className="min-w-0">
                  <p className="font-medium">{d.title}</p>
                  <p className="ui-meta">{categories[d.category] ?? d.category} · {d.filename} · {(d.size_bytes / 1024).toFixed(0)} KB
                    · {formatDate(d.uploaded_at)}{d.uploaded_by_email ? ` · ${d.uploaded_by_email}` : ""}</p>
                </div>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" icon={FileDown} onClick={() => void apiFetchBlob(`${base}/${encodeURIComponent(d.document_id)}/download`)
                    .then((blob) => downloadBlob(blob, d.filename)).catch((e) => toast.error(e, "Download failed"))}>Download</Button>
                  {project.can_manage && <Button size="sm" variant="ghost" icon={Trash2} loading={remove.isPending && remove.variables === d.document_id}
                    onClick={() => { if (window.confirm(`Remove "${d.title}" from the project documents?`)) remove.mutateAsync(d.document_id)
                      .then(() => toast.success("Document removed")).catch((e) => toast.error(e, "Couldn't remove the document")); }}>Remove</Button>}
                </div>
              </div>
            ))}
          </div>
        )}

        {project.can_contribute && (
          <form className="grid gap-2 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_auto]" onSubmit={(e) => {
            e.preventDefault();
            const file = fileRef.current?.files?.[0];
            if (!file) return;
            const form = new FormData();
            form.append("category", category);
            form.append("title", title);
            form.append("file", file);
            upload.mutateAsync(form).then(() => {
              setTitle(""); if (fileRef.current) fileRef.current.value = "";
              toast.success("Document uploaded", { description: categories[category] });
            }).catch((err) => toast.error(err, "Couldn't upload the document"));
          }}>
            <Select aria-label="Document type" value={category} onChange={(e) => setCategory(e.target.value)}>
              {Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </Select>
            <TextInput aria-label="Title (optional)" placeholder="Title (optional)" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
            <input ref={fileRef} type="file" required aria-label="File" className="text-sm sm:col-span-2"
              accept=".pdf,.docx,.png,.jpg,.jpeg,.webp,.csv,.txt,.json" />
            <Button type="submit" icon={Upload} loading={upload.isPending}>Upload</Button>
          </form>
        )}
      </>}
    </Card>
  );
}
