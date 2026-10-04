# Methodology source coverage implementation

## Changes

- Project Methodology shows source coverage for each pathway's server-resolved bundle, including current/stale/missing/external documents and correction mapping status. Read access uses existing project authorization.
- Product setup displays per-document ingestion outcomes, refreshes coverage after completion, and explains worker job types and PDF extraction prerequisites.
- Admins can inspect correction and target PDFs and explicitly confirm an existing curated mapping. No automatic confirmations; targets without a section/equation remain blocked.
- Indexing verifies the worker PDF against the registered hash, preserves an existing index on empty/failed extraction, detects file changes during extraction, and handles damaged PDFs independently. Database failures remain job failures.
- Ingestion checks cancellation between documents and maintains heartbeats. A completed ingestion job explicitly reports documents needing attention.
- Search and section retrieval exclude stale hashes and extraction versions. Correction retrieval also checks extraction version.
- Explanation drawers highlight deterministic source limitations and link to the project's coverage screen. Missing methodology text is distinct from missing project evidence.

## Operational use

Implementation does not populate the deployed database automatically. After deploying API/frontend changes, restart the updated local worker with:

```bash
python -m backend.worker --job-types ai_explain methodology_ingest
```

The worker must have the registered methodology PDFs and `pdftotext` available. In Product setup, choose **Index methodology PDFs**, inspect the per-document outcomes, then open Project → Methodology → AI source coverage. Request a new explanation after indexing. Unchanged documents are skipped.

An external reference cannot be indexed without a registered local PDF. Scanned PDFs without extractable text remain explicitly unavailable; this implementation does not introduce OCR or substitute another methodology version.

No tests, app startup, deployment, indexing jobs, or provider calls were run for this change, as requested. No equations, readiness decisions, project records, or correction confirmations were changed during implementation.
