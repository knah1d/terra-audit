# AI explanation evaluation tooling

Implemented canonical 20-case coverage, fixture-only packet export metadata,
preflight checks, per-attempt citation/forbidden-claim accounting, unique result
artifacts, provider-only latency summaries, and hash-bound human semantic review.

The evaluation contract lives in `src/ai/evaluation.py`, coverage in
`tests/ai_eval/manifest.json`, export in `scripts/ai_export_packet.py`, generation
in `scripts/ai_eval.py`, and semantic review in `scripts/ai_review_eval.py`.
See `tests/ai_eval/README.md` for operational commands.

No evaluations, tests, database fixture seeding, provider calls or deployment
were executed for this implementation. The 20 builder-generated packet files
remain to be exported from suitable disposable fixture state; a manifest is
not an executed evaluation and cannot establish provider quality.

Production equations, authorization, provider opt-in, readiness decisions and
AI action behavior are unchanged. Case 20 adds a hostile request solely inside
the offline evaluation wrapper. Structural validators cannot prove semantic
entailment; acceptance requires human review of actual outputs.
