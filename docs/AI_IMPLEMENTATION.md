# AI and product implementation handoff

## Implemented application features

- **Project → AI workspace**: project-scoped Random Forest/XGBoost training through the durable worker; immutable model versions, frozen reviewed training data, held-out evaluation, explicit activation/disable decisions, optimistic concurrency on activation changes, checksum-verified model artifacts, and downloadable evaluation records.
- **Crop predictions**: completed field-seasons, declared crop and district scope checks, satellite coverage checks, processing/software compatibility checks, minimum score threshold, retained source/model provenance, and explicit abstention. Predictions do not write accounting values or approvals.
- **Evidence assistant**: configurable OpenAI Responses API, structured answers, retained context, checked source identifiers and exact quotations, provider/model/usage metadata, daily organization request limits, and cited draft downloads. The assistant has no write tools. It retrieves project records and already extracted document text; it does not browse the web.
- **Document workflow**: existing field attachments can be extracted from text/scanned PDF, DOCX, UTF-8 text/CSV, and JPEG/PNG/WebP document photos. Automatic mode reads embedded text and uses visual transcription for PDF pages with fewer than 80 extracted characters. Visual mode transcribes every PDF page; text-only mode never sends page images. Proposals include source quotations; a lead confirms the observation value/time or rejects the proposal. OCR proposals additionally require confirmation against the original page. Confirmation appends a document-sourced observation atomically with its decision, and independent evidence review remains separate. Referenced documents, page transcripts, and provider provenance are retained.
- **Account flows**: admin-created single-use invitation links, recipient-selected passwords, emailed recovery links, hashed tokens, expiry, request limits, and session invalidation after password reset. Invitations are shared manually; the UI does not claim that an email was sent.
- **Permissions**: project membership changes require lead/admin authority. API role checks use current account state. New AI worker jobs recheck authorization before publishing.
- **Supporting code**: private S3-compatible storage option, atomic local file writes, bounded attachment reads, admin setup/onboarding page, and offline backup/restore utilities. None of these utilities were run against your application data.

Season corrections now keep their stable season identity in training and bulk collection; training excludes unfinished seasons and snapshots whose dates no longer match the current season.

## Code entry points

- `backend/routers/ai_workspace.py` — workspace API and document decisions.
- `backend/ai_job_handlers.py` — durable AI job execution.
- `src/ai/workspace.py` — record storage and activation history.
- `src/ai/managed_models.py` — training and inference.
- `src/ai/assistant.py` — grounded answers and document extraction.
- `src/ai/document_ocr.py` — page-preserving visual transcription and extraction modes.
- `src/account_access.py`, `backend/routers/account_access.py` — invitations and recovery.
- `frontend/app/(app)/projects/[projectId]/ai/page.tsx` — user-facing AI workflow.
- `frontend/app/(auth)/account-access/page.tsx` — invitation acceptance/recovery.

## Configuration contract (for your later setup)

The updated requirements include `pypdf` and `boto3`. New tables are created through the existing application initialization path. Configure your own provider/model and service settings later; this implementation does not provision, deploy, or call paid services on your behalf.

- `OPENAI_API_KEY` and `OPENAI_MODEL`: assistant/document provider; no model is assumed by default. Select a model supporting strict structured outputs through the Responses API.
- `OPENAI_VISION_MODEL`: explicit model for scanned-page/image transcription, supporting image/PDF input and structured outputs. No visual model is assumed. Text-only features still use `OPENAI_MODEL`.
- `AI_PROVIDER_REQUESTS_PER_DAY`: default 100 actual provider attempts per organization per UTC day, reserved immediately before each API call. Every OCR page and the subsequent proposal-generation call count separately. Failed calls consume a reservation; queued jobs cancelled before any API attempt do not. This is a request-count limit, not a dollar budget.
- `FRONTEND_PUBLIC_URL`: absolute frontend address for account links. Recovery uses the existing Brevo key and sender settings.
- `STORAGE_BACKEND`: `local` or `s3`. API and worker need the same stored artifacts. Existing objects are not migrated automatically when changing storage backends.
- S3 settings and account/provider placeholders are listed in `.env.example`; no secrets are placed in frontend code.

## Deliberate boundaries and unfinished research work

This is the implemented core of the next phases, not a claim that every roadmap item or crop is scientifically validated.

- The managed crop models currently use seasonal Sentinel statistics. **Presto/WorldCereal/OlmoEarth embeddings and fine-tuning are not implemented.** Their input preparation and checkpoint compatibility need a separate implementation; pretrained weights were not downloaded.
- Mixed crops can be recorded, but a multi-label classifier is not implemented. A model only supports the crop classes represented in its accepted training data, not every crop automatically.
- Probabilities are uncalibrated. A high score is not a validated probability of correctness. No automatic model promotion, cross-region validation claim, early-season inference, or carbon verification is made.
- Visual extraction handles at most 10 OCR pages per request, PDFs of at most 50 pages, attachments of at most 20 MB (the upload limit may be lower), and 80,000 extracted characters in total. It transcribes document text; it does not diagnose plants or identify crops from photographs. HEIC requires conversion before extraction. DOCX has a logical document unit labelled page 1, not reconstructed physical pagination or image extraction.
- Automatic OCR is a sparse-text heuristic and may miss scans/handwriting on pages with a substantial existing text layer. Visual mode addresses that case. OCR quotes are exact matches to the retained AI transcript, not proof of correctness against the original scan. Original-document download and a required reviewer confirmation support human verification.
- Citation checks verify source existence and exact quoted text. They do not prove that an AI interpretation is correct. Answers and report paragraphs remain drafts.
- Methodology-specific searchable knowledge libraries, multi-turn conversation memory, and automatic report-template generation remain separate work. Current retrieval is bounded lexical selection of project evidence and extracted documents.
- The legacy organization-level field APIs retain their existing access model. New AI APIs are project-scoped; this is not a complete rewrite of every older endpoint into project-only authorization.
- External account recovery email and AI calls require your configured services. Recovery rate limits see the connected backend peer; proxy-aware limits need your hosting configuration.
- The API and worker must retain matching ML package versions. Recorded version mismatches block inference and require retraining.

No test suite or deployment was run for this implementation. Earlier syntax/type/import checks preceded your instruction to stop testing; subsequent changes have not been executed. You own functional validation and Vercel/Railway work.

## Reference interfaces used

- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI file inputs](https://developers.openai.com/api/docs/guides/file-inputs)
- [OpenAI image inputs](https://developers.openai.com/api/docs/guides/images-vision)
- [AWS S3 upload interface](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/upload_fileobj.html)
- [WorldCereal PromethEO](https://github.com/WorldCereal/prometheo) — research reference; not integrated into the running feature pipeline.
