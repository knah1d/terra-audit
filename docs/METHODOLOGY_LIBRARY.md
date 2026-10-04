# Methodology sources for AI explanations

Registered PDF files and indexed text are separate. A registry entry alone does
not make PDF text available to the assistant. An empty `methodology_chunks`
table means explanations can cite readiness records but cannot cite PDF text.

## Index using the local computer

From the repository root, with the virtual environment active and `.env` pointing
to the same database as the API:

```bash
python scripts/ingest_methodologies.py --all
```

To index only VM0051:

```bash
python scripts/ingest_methodologies.py --document-id vm0051-v1.1
```

This maintenance command writes reference chunks, skips unchanged PDFs, and does
not run calculations, generate AI output, or change readiness decisions. Missing
registered local files cause a nonzero exit. It requires `pdftotext` from
`poppler-utils`; the backend Docker image installs this dependency.

## Index through Product setup

An administrator opens **Product setup → AI methodology library → Index
methodology PDFs**. The page displays the job status and document counts. Refresh
index status after completion. The ingestion job is organization-scoped; indexed
methodology text is a shared reference library. Explanation retrieval still uses
only the selected project's resolved bundle.

A worker started with only `--job-types ai_explain` cannot process ingestion.
When restarting your existing worker, use:

```bash
python -m backend.worker --job-types ai_explain methodology_ingest
```

Alternatively, use the maintenance command while keeping the AI-only worker
running. Do not start a duplicate worker just to run that command.

## After indexing

Request the explanation again. Indexed content participates in the evidence
fingerprint, so old cached explanations are not reused for the updated library.
An in-flight explanation may fail with an evidence-change message if indexing
finishes while it runs; request a new explanation after ingestion completes.

The assistant must retain the explicit missing-text limitation when a referenced
section is still unavailable. Indexing does not establish methodology compliance.
