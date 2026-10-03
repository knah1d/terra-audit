# Self-hosted evidence explanations

AI explains deterministic packets; it never approves readiness or computes
credits. Every returned answer is a draft requiring human review. RAG and
server validation remain active regardless of model provider.

## CPU development runtime

Download a llama.cpp release or build it using the upstream build instructions:
https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md

```bash
cmake -B build -DGGML_CUDA=OFF
cmake --build build --config Release --target llama-server -j 2
./build/bin/llama-server -m /path/to/model.gguf --host 127.0.0.1 --port 8080 -c 16384 -ngl 0
```

No model is hard-coded. Evaluate a 7–8B instruct Q4 GGUF candidate only after
checking its exact repository/revision, original model license, quantization
license, commercial terms, supported chat template, and schema behavior.
Context memory adds to weight memory; no hardware fit or performance is promised.

Set on both API and worker:

```dotenv
AI_PROVIDER=self_hosted
SELF_HOSTED_BASE_URL=http://localhost:8080
SELF_HOSTED_MODEL=your-server-model-name
SELF_HOSTED_SCHEMA_FORMAT=llama_cpp
SELF_HOSTED_TIMEOUT_SECONDS=600
SELF_HOSTED_MAX_TOKENS=2000
```

`SELF_HOSTED_BASE_URL` also accepts a base ending in `/v1`. For other compatible
servers use `SELF_HOSTED_SCHEMA_FORMAT=openai`. The provider keeps generation
schema-constrained in both modes. In OpenAI envelope mode, a recognized schema
format rejection can retry using llama.cpp's documented envelope; there is no
fallback to unconstrained text or JSON-only generation.

The upstream server documentation currently describes
`response_format: {type: "json_schema", schema: ...}` for chat completions.
Source checked 2026-10-04:
https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
The installed runtime has not been exercised: record `llama-server --version`
and run the evaluation on that exact version before enabling it for users.

## Deployed Vercel + Render setup

Localhost on Render means the Render container, not your laptop. For your
current workflow, point API and worker at a reachable model service instead.
Use HTTPS and an authenticated endpoint (`SELF_HOSTED_API_KEY`) for a remote
service. Vercel calls the Terra-Audit backend, not the model directly. Do not
expose an unauthenticated model server publicly. No model service has been
provisioned or deployed by this implementation.

For UI wiring without a model, set `AI_PROVIDER=fake` on API and worker. Fake
responses check pipeline behavior only; they do not demonstrate model quality.

## External-provider permission

OpenAI calls require an explicit organization-admin opt-in. After normal startup
creates the additive permission table, use the authenticated API:

```text
PUT /projects/{project_id}/ai/provider-permission
{"allowed": true}
```

This authorizes OpenAI for the whole organization, including OCR and the older
assistant. Revocation uses the same endpoint with false. A key alone grants no
permission. Cached explanations remain readable without a new provider call.

## Evaluation and hosted decision

Use `scripts/ai_eval.py` with frozen builder-exported packets. Complete the
coverage list in `tests/ai_eval/README.md`; synthetic placeholders are not
accepted as methodology or production proof. The evaluation is not run by this
implementation. Record before provider release:

| Measurement | Current result |
|---|---|
| Exact model/revision, license and commercial terms | Not selected |
| Runtime version / host | Not selected |
| Cold start / p50 / p95 | Not measured |
| Valid JSON / validation / forbidden claims / unknown citations | Not measured |
| Host retention terms and source/date | Not reviewed |

Targets: all outputs valid JSON; at least 90% validate within one retry; no
forbidden claims or citations to unsupplied sources. Do not turn an unmeasured
benchmark into a claimed pass.

## OCR decision

Keep scanned PDF/image extraction on the existing OpenAI-only path with
organization permission and visual human confirmation. Self-hosted explanation
is text-only. No replacement OCR was implemented. Future separate choices are
Tesseract, an evaluated local vision model, or disabling scanned documents.
