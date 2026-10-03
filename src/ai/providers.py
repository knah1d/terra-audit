"""Model provider abstraction for the evidence assistant.

AI_PROVIDER selects the backend:
  - "self_hosted": an OpenAI-compatible /v1/chat/completions server
    (e.g. llama.cpp `llama-server`, vLLM) at SELF_HOSTED_BASE_URL serving
    SELF_HOSTED_MODEL, with JSON-schema-constrained output.
  - "openai": the OpenAI Responses API (OPENAI_API_KEY/OPENAI_MODEL).
    Sends packets to a third party, so it is an explicit opt-in.
  - "fake": no model; returns the smallest schema-valid object. Lets the
    whole pipeline (packets, validation, queue, UI) run without a model.
If AI_PROVIDER is unset, "self_hosted" is used when SELF_HOSTED_BASE_URL
is set, else "openai" (preserves existing deployments).

Every provider returns (parsed_dict, provider_metadata). Quota
throttling is applied once, here, for every real provider call.
"""
import json
import os

import httpx


def provider_name() -> str:
    explicit = os.environ.get("AI_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    return "self_hosted" if os.environ.get("SELF_HOSTED_BASE_URL") else "openai"


def configured() -> bool:
    name = provider_name()
    if name == "fake":
        return True
    if name == "self_hosted":
        return bool(os.environ.get("SELF_HOSTED_BASE_URL") and os.environ.get("SELF_HOSTED_MODEL"))
    if name == "openai":
        return bool(os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENAI_MODEL"))
    return False


def _throttle(org_id: str) -> None:
    from src.account_access import throttle
    if not throttle("ai-provider:" + org_id, int(os.environ.get("AI_PROVIDER_REQUESTS_PER_DAY", "100")), 86400):
        raise ValueError("Organization AI daily provider-request limit reached")


def _parse_object(text: str) -> dict:
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("AI provider returned an invalid structured response")
    return parsed


def _openai(instructions, data, schema, org_id, media, vision):
    model = os.environ.get("OPENAI_VISION_MODEL") if vision else os.environ.get("OPENAI_MODEL")
    if not model:
        raise ValueError("Configure OPENAI_VISION_MODEL to extract scanned PDFs or images" if vision
                         else "Configure OPENAI_MODEL")
    _throttle(org_id)
    provider_input = json.dumps(data, default=str, allow_nan=False)
    if media:
        provider_input = [{"role": "user", "content": [{"type": "input_text", "text": provider_input}, *media]}]
    try:
        with httpx.Client(timeout=90) as client:
            response = client.post("https://api.openai.com/v1/responses", headers={
                "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"}, json={
                "model": model, "store": False, "max_output_tokens": 8000 if vision else 4000,
                "instructions": instructions, "input": provider_input,
                "text": {"format": {"type": "json_schema", "name": "evidence_response", "strict": True, "schema": schema}}})
        if response.status_code != 200:
            raise ValueError(f"AI provider request failed (HTTP {response.status_code}); check model configuration and account limits")
        body = response.json()
        if body.get("status") != "completed":
            raise ValueError("AI response was incomplete; shorten the request and try again")
        content = [c["text"] for item in body.get("output", []) if item.get("type") == "message"
                   for c in item.get("content", []) if c.get("type") == "output_text"]
        if len(content) != 1:
            raise ValueError("AI provider declined or returned no structured answer")
        parsed = _parse_object(content[0])
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise ValueError("AI provider is unavailable or returned an invalid response") from exc
    return parsed, {"provider": "openai", "model": body.get("model", model),
                    "response_id": body.get("id"), "usage": body.get("usage"), "store": False}


def _self_hosted(instructions, data, schema, org_id, media, vision):
    if media or vision:
        raise ValueError("The self-hosted provider is text-only; scanned-document OCR needs AI_PROVIDER=openai "
                         "or a separate OCR path")
    base_url = os.environ["SELF_HOSTED_BASE_URL"].rstrip("/")
    model = os.environ["SELF_HOSTED_MODEL"]
    _throttle(org_id)
    headers = {}
    if os.environ.get("SELF_HOSTED_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['SELF_HOSTED_API_KEY']}"
    try:
        with httpx.Client(timeout=float(os.environ.get("SELF_HOSTED_TIMEOUT_SECONDS", "600"))) as client:
            response = client.post(f"{base_url}/v1/chat/completions", headers=headers, json={
                "model": model, "temperature": 0, "max_tokens": int(os.environ.get("SELF_HOSTED_MAX_TOKENS", "2000")),
                "messages": [
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": json.dumps(data, default=str, allow_nan=False)},
                ],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "evidence_response", "strict": True, "schema": schema}},
                # Qwen3-family chat templates emit reasoning text unless
                # disabled; ignored by servers/templates that don't use it.
                "chat_template_kwargs": {"enable_thinking": False},
            })
        if response.status_code != 200:
            raise ValueError(f"Self-hosted model request failed (HTTP {response.status_code})")
        body = response.json()
        choice = (body.get("choices") or [{}])[0]
        if choice.get("finish_reason") not in (None, "stop"):
            raise ValueError("Self-hosted model response was truncated; shorten the request and try again")
        parsed = _parse_object(choice.get("message", {}).get("content") or "")
    except (httpx.HTTPError, json.JSONDecodeError, KeyError) as exc:
        raise ValueError("Self-hosted model is unavailable or returned an invalid response") from exc
    return parsed, {"provider": "self_hosted", "model": body.get("model", model),
                    "response_id": body.get("id"), "usage": body.get("usage"), "store": False}


def _minimal(schema):
    kind = schema.get("type")
    if isinstance(kind, list):
        return None if "null" in kind else _minimal({**schema, "type": kind[0]})
    if "enum" in schema:
        return schema["enum"][0]
    if kind == "object":
        return {k: _minimal(v) for k, v in schema.get("properties", {}).items()}
    if kind == "array":
        return []
    if kind == "string":
        return ""
    if kind in ("integer", "number"):
        return 0
    if kind == "boolean":
        return False
    return None


def _fake(instructions, data, schema, org_id, media, vision):
    if "summary_claims" in schema.get("properties", {}) and "packet" in data:
        return _fake_explanation(data["packet"]), {
            "provider": "fake", "model": "deterministic-fixture", "response_id": None,
            "usage": None, "store": False,
        }
    parsed = _minimal(schema)
    if isinstance(parsed, dict) and "limitations" in parsed:
        parsed["limitations"] = ["AI_PROVIDER=fake: no model was called; this is a pipeline placeholder."]
    return parsed, {"provider": "fake", "model": None, "response_id": None, "usage": None, "store": False}


def _fake_explanation(packet):
    """Exercise real citations/readiness links using supplied facts; no numeric invention."""
    sources = {s["id"]: s for s in packet["sources"]}
    result = {"summary_claims": [], "missing_evidence": [], "conflicts": [],
              "limitations": ["AI_PROVIDER=fake: no model was called; this checks the explanation pipeline."]}
    for fact in packet.get("facts", []):
        if fact["kind"] != "readiness":
            continue
        row = fact["data"]
        rid = row["requirement_id"]
        source = sources.get(f"readiness:{rid}")
        if not source or not source["sentences"]:
            continue
        ids = [s["id"] for s in source["sentences"][:10]]
        status = row.get("status")
        claim = (f"The supplied checklist marks {rid} as {status}." if status else
                 f"The supplied requirement {rid} has implementation support {row.get('implementation_support', 'not supplied')}.")
        if len(result["summary_claims"]) < 40:
            result["summary_claims"].append({"text": claim, "sentence_ids": ids})
        if status in {"missing", "needs_review", "unsupported"} and len(result["missing_evidence"]) < 40:
            result["missing_evidence"].append({"requirement_id": rid,
                "record_type": row["fix"]["record_type"], "explanation": claim, "sentence_ids": ids})
    if not result["summary_claims"]:
        chosen = next((s for s in sources.values() if s["kind"] == "leakage_assessment"), None)
        chosen = chosen or next((s for s in sources.values() if s["id"].endswith(":diff")), None)
        chosen = chosen or next((s for s in sources.values() if s["sentences"]), None)
        if chosen and chosen["sentences"]:
            result["summary_claims"].append({"text": "This draft explanation is based on the supplied records.",
                "sentence_ids": [chosen["sentences"][0]["id"]]})
    return result


_PROVIDERS = {"openai": _openai, "self_hosted": _self_hosted, "fake": _fake}


def generate(instructions, data, schema, *, org_id, media=None, vision=False):
    name = provider_name()
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown AI_PROVIDER {name!r}; use self_hosted, openai, or fake")
    if not configured():
        raise ValueError({
            "self_hosted": "Configure SELF_HOSTED_BASE_URL and SELF_HOSTED_MODEL on the API and worker",
            "openai": "Configure OPENAI_API_KEY and OPENAI_MODEL on the API and worker to enable the assistant",
        }.get(name, "AI provider is not configured"))
    return _PROVIDERS[name](instructions, data, schema, org_id, media, vision)
