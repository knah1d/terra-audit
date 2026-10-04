# Diagnosing explanation latency

Explanation timings use monotonic clocks. No prompts, record values, credentials
or provider response bodies are logged. Timing metadata never affects readiness.

After deploying the API and restarting the worker, request an explanation for
an item without a saved result. A cache hit returns the old generation metadata;
it does not call the provider again or create a new worker timing measurement.

## Render / API

The POST response contains `request_timings_seconds`: authorization,
packet_build, cache_lookup, enqueue (for a new job), and total. Total includes
permission and idempotency lookups as well. This isolates request preparation
from the worker's subsequent processing time.

## Local worker

Terminal logs have `ai_explain scope=worker job=<id> stage=<name>` and duration
in seconds. Stages are initial_packet_and_checkpoint, existing_record_lookup,
generation_and_validation, final_evidence_and_authorization_check, and save.

The saved explanation includes `generation_timings_seconds`, with separate
provider and validation durations for each attempt. Provider time includes
permission/quota checks, the HTTP call and response parsing. This is not merely
the model inference time reported by Groq's usage statistics.

The saved explanation's `worker_timings_seconds` covers stages through the final
checkpoint, before the immutable record is saved. Save duration and the complete
worker total are in logs and the job result; the existing record is never edited
just to attach a final timer.

Queue waiting time is the database's `locked_at - created_at`, separate from the
above durations. API and worker totals must not be added to provider time again:
generation_and_validation already includes the nested provider/validation stages.

If packet/checkpoint times dominate, optimize the evidence/readiness/database
queries while retaining authorization, active membership, bundle scoping and
fingerprint checks. If provider time dominates, inspect rate limits, context size,
reasoning/output token usage and retries. No latency improvement is claimed from
adding instrumentation alone.

## Packet optimization

Explanation packet reads now share one database connection in an explicitly
read-only scope, avoiding a separate transaction/rollback for every small helper.
The scope stores no query results. PostgreSQL uses READ COMMITTED so the packet's
last fingerprint pass can still observe concurrent commits; SQLite query-only
mode is restored before the connection returns to the pool. Context-local state
keeps different requests and the worker heartbeat thread isolated.

Monitoring tables are read with one organization/field-scoped UNION ALL.
Methodology index rows for bundle documents use one expanding IN query. Soil
plan/sample/lab/custody provenance uses at most five scoped queries instead of
queries per sample. Canonical row ordering retains the previous fingerprint
representation. Requirement metadata already in the fingerprinted state is
reused during citation construction.

The initial worker checkpoint still rebuilds and compares the complete packet.
The final checkpoint rechecks cancellation, provider identity, live authorization,
active field membership and all evidence/index/correction fingerprint values,
without rebuilding readiness, sentence IDs and citation retrieval. Database
connections are closed before provider calls or writes. No checks have been
replaced with a time-based cache. Measure a newly generated explanation after
deploying/restarting; the actual speed improvement is not yet verified.
