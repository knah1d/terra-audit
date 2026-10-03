# Phase 4A implementation handoff: steps 3–11

Updated: 2026-10-03. This document tracks the staged implementation of the
user-provided handoff. Provider switching, PDF indexing and library endpoints
already exist and are reused.

## Invariants

- Code determines readiness, gates and numeric results. AI only explains.
- Every generated explanation must be `draft_requires_human_review`.
- Authorization is rechecked using `workspace.authorize`; the field must be active
  in the selected project. All project records are organization-scoped.
- Methodology text comes only from documents in the project's resolved bundle.
  Historical calculation text also requires matching stored document hashes.
- Missing inputs remain missing; an explanation never substitutes zero.
- Migrations preserve existing data. No deployment is included.

## Step 3: correction-aware retrieval — implemented

`src/methodology_corrections.py` contains one manifest entry for each of the
12 VM0042 items and three VT0014 items. PDF pages, target sections, original
equation numbers and summaries are curated from the two local correction PDFs.
All entries start as draft. Summaries are metadata, not verbatim PDF quotations.

`methodology_library.initialize_tables` creates the reference-link table and an
organization-scoped confirmation table. Confirmations pin the mapping and both
document hashes. Restart preserves current confirmations; changed mappings or
hashes return to an unconfirmed effective status. A confirmation approves the
mapping only and never changes readiness.

Endpoints:

- `GET /methodology/corrections?document_id=...`
- `POST /methodology/corrections/{id}/confirm` (organization admin)

Reference retrieval and search attach correction excerpts, including items that
span pages. Excerpts stop at the next item even when two items share a page.
Missing, stale or outside-bundle correction text is explicitly flagged; the
affected original cannot be used alone. Draft mappings retain their unconfirmed
label. Redlines and equations require visual PDF review because `pdftotext`
retains struck-out material and can lose mathematical formatting and figures.

Appendix headings are indexed. Existing indexes reingest once under parser
version 2 using the normal ingest endpoint; subsequent identical ingestion skips.
VT0014 is registered but is not added to the existing ALM bundle by this work.

Verification: nine focused correction tests passed using temporary SQLite data.
The API checks needed execution outside the sandbox because TestClient's event
loop could not start inside it. PostgreSQL integration has not been exercised.

## Step 4: sentence IDs and action packets — implemented

`src/ai/packets.py` provides:

- `split_sentences(source_id, text)` with deterministic IDs, separate list/table
  rows, and pieces of at most 400 characters.
- `explain_block`: stored results, engine gate reason, blocking readiness rows,
  frozen project evidence, section references and corrections.
- `missing_evidence`: live checklist, optional requirement filter, and server-owned
  record types and routes from `REQUIREMENT_FIX_MAP`.
- `applicable_requirements`: project-specific enrollment and bundle requirements.
- `explain_leakage`: stored calculation leakage, or the existing deterministic
  calculator operating on an authorized saved assessment and captured records.
- `diff_since_previous`: the same pure comparison used by submission reviews.
  No predecessor returns `call_model: false` and "No previous version".

Packets contain structured facts, citable sentences, allowed IDs, provenance,
`context_sha256`, and a separate live `evidence_fingerprint`. Fingerprints cover
full field evidence, raw soil samples, labs, custody, reviews, production data,
assessments, calculation state, methodology indexing and correction confirmation.
Authorization and evidence are checked again after building the packet.

The default budget is 12k estimated tokens to leave room in a 16k model context
for instructions, schema and response. Budgets cannot exceed 16k. Lower-priority
methodology references are removed first and recorded as omitted. Essential
facts and record sentences are retained; oversized essential data produces an
explicit error. Raw redlined correction excerpts are reference material;
citable correction sentences identify the curated mapping and its review state.

Existing calculation snapshots remain immutable. Current text is omitted where
the stored and current bundle/document hashes differ. Missing verification years
are described as needing review rather than silently adopting the checklist's
legacy one-year default.

The default methodology resolver now returns full document lists and hashes,
matching the explicitly pinned resolver. Historical-lookback and rotation
references include their actual Section 6 anchor. Guided enrollment accepts an
optional project ID so applicability packets respect project-specific pins.
Submission diffs reuse a pure calculation comparison; changed requirements
remain allowed even when removed from the current calculation.

Verification runs use temporary databases. The backend/frontend integration,
response validation and model generation belong to the subsequent stages.

## Remaining implementation order

| Step | Deliverable | Completion check |
| --- | --- | --- |
| 5 | Strict response schema, sentence/identifier/number validation, prohibited claims, server-resolved citations, one retry; migrate existing `answer()` last | Reject unknown citations, unsupported numeric claims and compliance declarations without returning partial output |
| 6 | Authorized `ai_explain` jobs, immutable storage, tenant/project cache, request/status/history endpoints and quota handling | Recheck authorization and evidence at job start and before save; cache hits make no provider request |
| 7 | Polling hook, shared explanation drawer, calculation/readiness/leakage buttons and citation/fix links | Complete blocked-calculation workflow with draft label using the fake provider |
| 8 | `AI_SELF_HOSTED.md`, llama.cpp setup and narrowly scoped structured-output compatibility handling | Verify compatibility on the installed server; do not silently fall back to unconstrained generation |
| 9 | Twenty fixture-backed packets and evaluation runner with CSV/summary output | Valid JSON in all cases, at least 90% validate within one retry, no forbidden claims or unknown citations |
| 10 | Central organization-level OpenAI opt-in and actual hosted/provider comparisons | Record actual model/license, cold start, p50/p95 latency, validation rates and retention terms |
| 11 | Record OCR decision separately; retain current OpenAI-only OCR behavior | Self-hosted explanations work without an OpenAI key; OCR availability is separately disclosed |

OpenAI opt-in enforcement belongs before any new paid provider call, even though
benchmark documentation is Step 10. Cache identity must distinguish provider,
model, prompt/schema revision and correction state so fake responses cannot be
reused as real-model explanations.

Live model and serverless-GPU benchmarks require configured endpoints, a selected
model and license, and organization permission. Unexecuted comparisons must remain
pending. Fake-provider checks establish pipeline structure, not model quality.

## Final proof points

Keep the handoff's P1–P11 checks: ingestion idempotency and counts; bundle-scoped
liming retrieval; VMD0054 page reference; all correction items; stable packet
hashes and invalidation; validator negative/normalization cases; two-tenant
isolation; no readiness/status writes; fake-provider UI; real-provider quality;
and final backend/frontend checks. Record each result only after running it.
