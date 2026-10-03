"use client";
import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

export type Explanation = {
  summary_claims: { text: string; sentence_ids: string[] }[];
  missing_evidence: { requirement_id: string; explanation: string; route?: string | null }[];
  conflicts: { description: string }[];
  limitations: string[];
  context_sha256: string;
  provider: { provider: string; model?: string | null };
  deterministic_message?: string;
  citations_resolved: { sentence_id?: string; id?: string; text: string; title?: string; document_id?: string; page?: number; route?: string; label?: string }[];
};

export function useAiExplain(projectId: string) {
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  useEffect(() => () => { generation.current += 1; }, [projectId]);
  async function request(body: Record<string, unknown>) {
    const current = ++generation.current;
    setLoading(true); setError(null); setExplanation(null);
    try {
      const result = await apiFetch<{ explanation?: Explanation; job_id?: string }>(`/projects/${projectId}/ai/explain`, { method: "POST", json: body });
      if (current !== generation.current) return;
      if (result.explanation) { setExplanation(result.explanation); return; }
      if (!result.job_id) throw new Error("Explanation request returned no job");
      while (current === generation.current) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        if (current !== generation.current) return;
        const job = await apiFetch<{ status: string; explanation?: Explanation; error?: string }>(`/projects/${projectId}/ai/explain/jobs/${result.job_id}`);
        if (current !== generation.current) return;
        if (job.status === "done") { setExplanation(job.explanation ?? null); return; }
        if (["error", "failed", "cancelled"].includes(job.status)) throw new Error(job.error || "Explanation could not be generated");
      }
    } catch (cause) {
      if (current === generation.current) setError(cause instanceof Error ? cause.message : "Explanation failed");
    } finally { if (current === generation.current) setLoading(false); }
  }
  return { request, explanation, error, loading };
}
