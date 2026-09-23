"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface AIRecord<T = Record<string, unknown>> { id: string; kind: string; created_at: string; payload: T }
export interface ModelData {
  name: string; model: string; classes: string[]; districts: string[]; calibration: string;
  evaluation: { split: string; models: Record<string, { report: Record<string, { f1_score?: number; "f1-score"?: number; support?: number }>; brier_score: number; log_loss: number }> };
}
export interface PredictionData { field_id: string; season_id: string; predicted_crop: string | null; confidence: number | null; status: string; reasons: string[]; in_training_data: boolean; model_id: string }
export interface AnswerData { question: string; claims: { text: string; citations: { source_id: string; quote: string }[] }[]; limitations: string[]; omitted_sources: number; sources: { id: string; title: string; text: string; truncated: boolean }[] }
export interface DocumentData {
  filename: string; field_id: string; season_id: string;
  proposals: { kind: string; value: string; observed_at: string | null; page: number; quote: string; requires_visual_confirmation?: boolean }[];
  limitations: string[];
  pages: { page: number; text: string; extraction_method?: string; warnings?: string[] }[];
  extraction?: { mode: string; ocr_pages: number[]; page_count: number };
}
export interface Workspace {
  records: AIRecord[];
  deployment: { model_id: string | null; revision: number; threshold: number };
  assistant_configured: boolean; vision_configured: boolean; can_manage: boolean;
  seasons: { field_id: string; field_name: string; season_id: string; name: string; crops: string[] }[];
  attachments: { attachment_id: string; field_id: string; filename: string; content_type: string }[];
  jobs: { job_id: string; status: string; job_type: string; error: string | null; created_at: string }[];
}
export function useAIWorkspace(project: string) {
  return useQuery({ queryKey: ["ai-workspace", project], queryFn: () => apiFetch<Workspace>(`/projects/${project}/ai`),
    refetchInterval: q => q.state.data?.jobs.some(j => ["pending", "running", "cancel_requested"].includes(j.status)) ? 2500 : false });
}
export function useAIAction(project: string) {
  const client = useQueryClient();
  return useMutation({ mutationFn: ({ path, body, method = "POST" }: { path: string; body?: unknown; method?: string }) =>
    apiFetch(`/projects/${project}/ai${path}`, { method, json: body }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["ai-workspace", project] }) });
}

export function useAICorpus(project: string) {
  return useQuery({ queryKey: ["ai-corpus", project],
    queryFn: () => apiFetch<{ examples: { crop: string }[]; excluded: { season_id: string; reason: string }[] }>(`/projects/${project}/ai/corpus`) });
}
