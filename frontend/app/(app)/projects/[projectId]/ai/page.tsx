"use client";
import { useState } from "react";
import { apiFetchBlob } from "@/lib/api";
import { useProjectContext } from "@/components/projects/ProjectContext";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Select, TextInput, TextArea } from "@/components/ui/Field";
import { useAIWorkspace, useAIAction, useAICorpus, AIRecord, ModelData, PredictionData, AnswerData, DocumentData } from "@/hooks/use-ai-workspace";

function download(value: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}

export default function AIWorkspacePage() {
  const project = useProjectContext();
  const query = useAIWorkspace(project.project_id);
  const corpus = useAICorpus(project.project_id);
  const action = useAIAction(project.project_id);
  const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const [name, setName] = useState(""); const [model, setModel] = useState("random_forest"); const [split, setSplit] = useState("field");
  const [chosenModel, setChosenModel] = useState(""); const [threshold, setThreshold] = useState("0.8"); const [reason, setReason] = useState("");
  const [seasonId, setSeasonId] = useState(""); const [attachmentId, setAttachmentId] = useState(""); const [question, setQuestion] = useState("");
  const [extractionMode, setExtractionMode] = useState("auto");
  const data = query.data;
  async function run(path: string, body?: unknown, method = "POST") {
    setError(""); setNotice("");
    try { await action.mutateAsync({ path, body, method }); setNotice(path.includes("review") || path === "/deployment" ? "Saved." : "Request queued. Progress appears below."); }
    catch (e) { setError(e instanceof Error ? e.message : "Request failed"); throw e; }
  }
  const dispatch = (path: string, body?: unknown, method?: string) => { void run(path, body, method).catch(() => {}); };
  async function downloadOriginal(id: string, filename: string) {
    setError("");
    try {
      const blob = await apiFetchBlob(`/projects/${project.project_id}/ai/documents/${id}/source`);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = url; link.download = filename; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(e instanceof Error ? e.message : "Original document could not be downloaded"); }
  }
  if (query.isLoading) return <p>Loading AI workspace…</p>;
  if (query.error || !data) return <p role="alert">{query.error?.message ?? "Workspace unavailable"}</p>;
  const models = data.records.filter(r => r.kind === "model") as unknown as AIRecord<ModelData>[];
  const predictions = data.records.filter(r => r.kind === "prediction") as unknown as AIRecord<PredictionData>[];
  const answers = data.records.filter(r => r.kind === "answer") as unknown as AIRecord<AnswerData>[];
  const documents = data.records.filter(r => r.kind === "document") as unknown as AIRecord<DocumentData>[];
  const chosenSeason = data.seasons.find(s => s.season_id === seasonId);
  const disabled = !data.can_manage || action.isPending;
  return <div className="space-y-5">
    <p className="text-sm text-text-secondary">Multi-crop AI supports monitoring and evidence preparation. Model scores are uncalibrated; outputs require human review and do not authorize carbon credits.</p>
    {!data.can_manage && <p className="text-sm">Project leads and organization admins can run AI workflows. You can view saved results.</p>}
    {(error || query.error) && <p role="alert" className="text-danger-700">{error}</p>}
    {notice && <p role="status" className="text-success-700">{notice}</p>}
    <Card><h2 className="mb-3 font-semibold">Train a crop model</h2>
      <p className="mb-3 text-sm text-text-secondary">Requires at least four eligible field-seasons, two crops, and independently reviewed labels. Training uses only active project fields and reserves independent groups for evaluation.</p>
      {corpus.error && <p role="alert" className="mb-3 text-sm text-danger-700">{corpus.error.message}</p>}
      {corpus.data && <details className="mb-3 text-sm"><summary>{corpus.data.examples.length} eligible seasons · {new Set(corpus.data.examples.map(e => e.crop)).size} crops · {corpus.data.excluded.length} excluded seasons</summary>{corpus.data.excluded.map(e => <p className="mt-1" key={e.season_id}>{data.seasons.find(s => s.season_id === e.season_id)?.name ?? e.season_id}: {e.reason}</p>)}</details>}
      <form className="grid gap-3 sm:grid-cols-4" onSubmit={e => { e.preventDefault(); dispatch("/train", { name, model, split }); }}>
        <label className="text-sm">Version name<TextInput required maxLength={120} value={name} onChange={e => setName(e.target.value)} placeholder="September crop baseline" /></label>
        <label className="text-sm">Model<Select value={model} onChange={e => setModel(e.target.value)}><option value="random_forest">Random forest</option><option value="xgboost">XGBoost</option></Select></label>
        <label className="text-sm">Hold out by<Select value={split} onChange={e => setSplit(e.target.value)}><option value="field">Field</option><option value="year">Year</option><option value="district">District</option></Select></label>
        <Button type="submit" disabled={disabled}>Train and evaluate</Button>
      </form>
    </Card>
    <Card><h2 className="mb-3 font-semibold">Model versions</h2>
      {!models.length && <p className="text-sm">No trained versions yet.</p>}
      {models.map(r => { const metric = r.payload.evaluation.models[r.payload.model]; return <div key={r.id} className="border-t border-border py-3 text-sm">
        <div className="flex flex-wrap justify-between gap-2"><strong>{r.payload.name}{data.deployment.model_id === r.id ? " · Active" : " · Candidate"}</strong><Button size="sm" variant="secondary" onClick={() => download(r, `model-${r.id}.json`)}>Download evaluation</Button></div>
        <p>{r.payload.classes.join(", ")} · {r.payload.districts.join(", ")} · Holdout: {r.payload.evaluation.split}</p>
        <p>Macro F1: {metric?.report["macro avg"]?.["f1-score"]?.toFixed(3) ?? "—"} · Brier score: {metric?.brier_score.toFixed(3)} · Log loss: {metric?.log_loss.toFixed(3)}</p>
      </div>; })}
      <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={e => { e.preventDefault(); dispatch("/deployment", { model_id: chosenModel || null, threshold: Number(threshold), expected_revision: data.deployment.revision, reason }, "PUT"); }}>
        <label className="text-sm">Active model<Select value={chosenModel} onChange={e => setChosenModel(e.target.value)}><option value="">Disable predictions</option>{models.map(m => <option key={m.id} value={m.id}>{m.payload.name}</option>)}</Select></label>
        <label className="text-sm">Minimum model score<TextInput required type="number" min="0.5" max="1" step="0.01" value={threshold} onChange={e => setThreshold(e.target.value)} /></label>
        <label className="text-sm">Reason for activation or change<TextInput required minLength={5} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <Button type="submit" disabled={disabled}>Save activation decision</Button>
      </form>
      <p className="mt-2 text-xs text-text-secondary">Current revision: {data.deployment.revision}; threshold: {data.deployment.threshold}. Activation records your decision; it does not establish regional validity.</p>
      <details className="mt-3 text-sm"><summary>Activation history</summary>{data.records.filter(r => r.kind === "deployment").map(r => <p key={r.id}>{new Date(r.created_at).toLocaleString()} · {String(r.payload.reason)} · revision {String(r.payload.revision)}</p>)}</details>
    </Card>
    <Card><h2 className="mb-3 font-semibold">Analyze a field-season</h2>
      <label className="text-sm">Crop season<Select value={seasonId} onChange={e => { setSeasonId(e.target.value); setAttachmentId(""); }}><option value="">Select a field-season</option>{data.seasons.map(s => <option key={s.season_id} value={s.season_id}>{s.field_name} · {s.name} · {s.crops.join(", ")}</option>)}</Select></label>
      <Button className="mt-3" disabled={disabled || !chosenSeason || !data.deployment.model_id} onClick={() => chosenSeason && dispatch("/predict", { field_id: chosenSeason.field_id, season_id: seasonId })}>Predict crop from satellite evidence</Button>
      {predictions.map(r => <div key={r.id} className="mt-3 border-t border-border pt-3 text-sm"><strong>{r.payload.predicted_crop ?? "Insufficient evidence"}</strong> · {r.payload.field_id} · {r.payload.confidence === null ? "No score" : `${(r.payload.confidence * 100).toFixed(1)}% model score`}
        {r.payload.reasons.map(x => <p key={x}>{x}</p>)}{r.payload.in_training_data && <p className="text-warning-700">This field was represented in training; this result is not an independent evaluation.</p>}
        <Button size="sm" variant="ghost" onClick={() => download(r, `prediction-${r.id}.json`)}>Download provenance</Button></div>)}
    </Card>
    <Card><h2 className="mb-3 font-semibold">Document proposals</h2>
      <p className="mb-2 text-sm text-text-secondary">Select an attachment already uploaded to the chosen field or season. PDF, DOCX, UTF-8 text/CSV, JPEG, PNG, and WebP are supported. Text is sent to the configured OpenAI model; visual extraction also sends the selected page images or document photo.</p>
      {!data.assistant_configured && <p className="mb-2 text-warning-700">Assistant is disabled. Configure OPENAI_API_KEY and OPENAI_MODEL on the API and worker.</p>}
      <Select aria-label="Document" value={attachmentId} onChange={e => setAttachmentId(e.target.value)}><option value="">Select a document</option>{data.attachments.filter(a => a.field_id === chosenSeason?.field_id).map(a => <option key={a.attachment_id} value={a.attachment_id}>{a.filename}</option>)}</Select>
      <label className="mt-3 block text-sm">Extraction method<Select value={extractionMode} onChange={e => setExtractionMode(e.target.value)}><option value="auto">Automatic: text with OCR for sparse pages</option><option value="text">Text only: no images or handwriting</option><option value="vision" disabled={!data.vision_configured}>Visual: read every PDF page or image</option></Select></label>
      <p className="mt-2 text-xs text-text-secondary">Up to 10 visual pages per request. Choose visual mode when handwritten or scanned content appears beside existing text. Each visual page uses one provider request.</p>
      {!data.vision_configured && <p className="mt-2 text-sm text-warning-700">Visual extraction is unavailable until OPENAI_VISION_MODEL is configured.</p>}
      <Button className="mt-3" disabled={disabled || !data.assistant_configured || !chosenSeason || !attachmentId} onClick={() => chosenSeason && dispatch("/documents", { field_id: chosenSeason.field_id, season_id: seasonId, attachment_id: attachmentId, extraction_mode: extractionMode })}>Extract proposals</Button>
      {documents.map(doc => <div key={doc.id} className="mt-4 border-t border-border pt-3"><h3 className="font-medium">{doc.payload.filename}</h3>
        <Button size="sm" variant="secondary" className="my-2" onClick={() => { void downloadOriginal(doc.id, doc.payload.filename); }}>Download original for review</Button>
        {doc.payload.limitations.map((x, i) => <p className="text-sm" key={i}>{x}</p>)}
        <details className="my-3 text-sm"><summary>Page transcripts and extraction notes</summary>{doc.payload.pages.map(page => <div key={page.page} className="mt-2 rounded border border-border p-2"><strong>Page {page.page} · {page.extraction_method === "vision_ocr" ? "AI OCR — confirm against original" : "Embedded text"}</strong>{page.warnings?.map((w, i) => <p className="text-warning-700" key={i}>{w}</p>)}<pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-sans">{page.text || "No readable text"}</pre></div>)}</details>
        {!doc.payload.proposals.length && <p className="text-sm">No supported observations found.</p>}
        {doc.payload.proposals.map((p, i) => <Proposal key={i} proposal={p} disabled={disabled} reviewed={data.records.find(r => r.kind === "document_review" && r.payload.document_id === doc.id && r.payload.proposal_index === i)?.payload.decision as string | undefined}
          onReview={body => run(`/documents/${doc.id}/proposals/${i}/review`, body)} />)}
      </div>)}
    </Card>
    <Card><h2 className="mb-3 font-semibold">Evidence assistant</h2>
      <p className="mb-2 text-sm text-text-secondary">Ask about project evidence, missing records, or a draft report. Relevant project records are sent to OpenAI. Every saved factual claim includes a source quote; review its meaning before using it.</p>
      <form onSubmit={e => { e.preventDefault(); dispatch("/ask", { question }); }} className="space-y-3">
        <TextArea aria-label="Question" required minLength={3} maxLength={4000} rows={3} placeholder="Summarize the evidence gaps for this project, citing sources." value={question} onChange={e => setQuestion(e.target.value)} />
        <Button type="submit" disabled={disabled || !data.assistant_configured}>Ask assistant</Button>
      </form>
      {answers.map(r => <div key={r.id} className="mt-4 border-t border-border pt-3 text-sm"><h3 className="font-semibold">{r.payload.question}</h3>
        {r.payload.claims.map((c, i) => <div key={i} className="mt-3"><p className="whitespace-pre-wrap">{c.text}</p><details className="mt-1 text-text-secondary"><summary>Sources ({c.citations.length})</summary>{c.citations.map((s, n) => <blockquote key={n} className="my-2 border-l-2 border-brand-500 pl-3"><p>{r.payload.sources.find(x => x.id === s.source_id)?.title} · {s.source_id}</p><p className="whitespace-pre-wrap">{s.quote}</p></blockquote>)}</details></div>)}
        {r.payload.limitations.map((x, i) => <p key={i} className="mt-2 text-warning-700">{x}</p>)}
        {r.payload.omitted_sources > 0 && <p>{r.payload.omitted_sources} sources were outside this response’s context limit.</p>}
        <Button size="sm" variant="secondary" className="mt-3" onClick={() => download(r, `draft-${r.id}.json`)}>Download cited draft</Button>
      </div>)}
    </Card>
    <Card><h2 className="mb-3 font-semibold">Recent jobs</h2>{!data.jobs.length && <p className="text-sm">No AI jobs yet.</p>}{data.jobs.map(j => <div key={j.job_id} className="flex flex-wrap items-center justify-between gap-2 border-t border-border py-2 text-sm"><span>{j.job_type.replace("workspace_", "")} · {j.status} · {new Date(j.created_at).toLocaleString()}{j.error && <span className="block text-danger-700">{j.error}</span>}</span>{["pending", "running"].includes(j.status) && <Button size="sm" variant="secondary" disabled={disabled} onClick={() => dispatch(`/jobs/${j.job_id}/cancel`)}>Cancel</Button>}</div>)}</Card>
  </div>;
}

function Proposal({ proposal, reviewed, disabled, onReview }: { proposal: DocumentData["proposals"][number]; reviewed?: string; disabled: boolean; onReview: (body: unknown) => Promise<void> }) {
  const [value, setValue] = useState(proposal.value); const [date, setDate] = useState(""); const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  return <div className="mt-3 rounded-lg border border-border p-3 text-sm"><p>{proposal.kind.replaceAll("_", " ")} · page {proposal.page}</p><blockquote className="my-2 border-l-2 pl-3">{proposal.quote}</blockquote>
    {reviewed ? <p>Proposal {reviewed}. Accepted observations still require independent evidence review.</p> : <form className="space-y-2" onSubmit={e => { e.preventDefault(); void onReview({ decision: "accepted", value, observed_at: date ? new Date(date).toISOString() : null, reason, confirmed_against_original: confirmed }).catch(() => {}); }}>
      <label className="block">Observation value<TextInput value={value} required maxLength={500} onChange={e => setValue(e.target.value)} /></label>
      <label className="block">Confirm date and time (your local timezone)<TextInput type="datetime-local" value={date} required onChange={e => setDate(e.target.value)} /></label>
      <label className="block">Review reason<TextInput value={reason} required minLength={3} onChange={e => setReason(e.target.value)} /></label>
      {proposal.requires_visual_confirmation && <label className="flex items-start gap-2"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} required /><span>I checked this OCR quote and observation against page {proposal.page} of the original document.</span></label>}
      <div className="flex gap-2"><Button type="submit" size="sm" disabled={disabled || (proposal.requires_visual_confirmation && !confirmed)}>Add document observation</Button><Button type="button" size="sm" variant="secondary" disabled={disabled || reason.trim().length < 3} onClick={() => { void onReview({ decision: "rejected", reason }).catch(() => {}); }}>Reject proposal</Button></div>
    </form>}
  </div>;
}
