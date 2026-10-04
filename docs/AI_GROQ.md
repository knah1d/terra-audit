# Groq draft explanations

The existing queue, evidence fingerprint, authorization and sentence validator
remain authoritative. Groq generates text drafts only; OCR remains separate.
The adapter uses strict JSON schema at `/openai/v1/chat/completions` as documented
at https://console.groq.com/docs/structured-outputs.

## Local worker

Set these in the untracked root `.env`:

```dotenv
AI_PROVIDER=groq
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=openai/gpt-oss-20b
GROQ_API_KEY=<private key>
```

Keep the same hosted `DATABASE_URL` as Render. Optional settings:
`GROQ_TIMEOUT_SECONDS=120`, `GROQ_MAX_TOKENS=8000`.

Stop the existing worker with Ctrl+C and restart after updating code/env:

```bash
source venv/bin/activate
python -m backend.worker --job-types ai_explain
```

## Render API

Push the implementation, then set the same `AI_PROVIDER`, `GROQ_BASE_URL` and
`GROQ_MODEL` on Render. The explanation enqueue endpoint does not require the
API key: only the worker executing the request needs it. Leave the existing
database and production URL settings intact. Never put the key in a public
frontend variable.

## Organization permission

An authenticated organization admin enables Groq via:

```http
PUT /projects/{project_id}/ai/provider-permission
Content-Type: application/json

{"provider":"groq","allowed":true}
```

Check with `GET /projects/{project_id}/ai/provider-permission?provider=groq`.
This opts the organization into sending supplied evidence to Groq.

## Request a fresh explanation

Use a blocked calculation's Explain button. The drawer must identify `groq`
and the configured model. Cache and job identities include provider, model,
endpoint, schema and prompt version, so fake results are not reused.
API and worker identity must match; mismatches fail without publishing a draft.
Rate limits, refusals, truncation and invalid citations remain explicit errors;
there is no fallback to fake or unconstrained output.

## Evaluation still outstanding

The runner supports `python scripts/ai_eval.py --provider groq`, but the twenty
frozen cases must first be created. No model quality or deployment verification
is claimed merely from adding this adapter.

If a key has been pasted into chat, rotate it in Groq and replace the local
`GROQ_API_KEY`, then restart the worker.
