import copy

import pytest

from src.ai.validate import ExplanationValidationError, generate_explanation, validate_response


def packet(text="Measured value = 12.3 tCO2e."):
    return {"org_id": "org", "context_sha256": "hash", "allowed_record_ids": ["sample-a"],
            "allowed_requirement_ids": ["vm0042.soc_measurements"], "limitations": [],
            "sources": [{"id": "source", "title": "Record", "kind": "soil_sample", "sentences": [
                {"id": "source:s1", "text": text}]}],
            "facts": [{"kind": "readiness", "data": {
                "requirement_id": "vm0042.soc_measurements", "status": "missing",
                "fix": {"record_type": "soil_evidence_review", "route": "/fields/f/soil-evidence", "fix_available": True}}}]}


def response(text="The measured value is 12.3 tCO2e.", ids=None):
    return {"summary_claims": [{"text": text, "sentence_ids": ids if ids is not None else ["source:s1"]}],
            "missing_evidence": [], "conflicts": [], "limitations": []}


@pytest.mark.parametrize("text,claim", [
    ("Value = 1,000 ha.", "Value is 1000 ha."),
    ("Value = 1000 ha.", "Value is 1,000 ha."),
    ("Rate = 12%.", "Rate is 0.12."),
    ("Rate = 0.12.", "Rate is 12%."),
    ("Value = -12.3 tCO2e.", "Value is -12.3tCO2e."),
    ("Value = 1.0.", "Value is 1.0000000005."),
    ("Eq. 53 applies in §5.4, Step 3 on 2026-01-01.", "Equation 53 applies in §5.4, Step 3 in 2026."),
])
def test_supported_numeric_formats(text, claim):
    result = validate_response(response(claim), packet(text))
    assert result["validation"]["passed"] and result["status"] == "draft_requires_human_review"
    assert result["citations_resolved"][0]["text"] == text


@pytest.mark.parametrize("claim", ["Value is 999 tCO2e.", "Value is 12.3 ha.", "Value is -12.3 tCO2e.",
    "Value is 999tCO2e.", "Equation 12 applies.", "The project is compliant.", "This is approved.",
    "The field is eligible for issuance.", "The field is certified.", "soil_sample:invented is present.",
    "vm0042.invented is missing."])
def test_unsupported_and_prohibited_claims_are_rejected(claim):
    with pytest.raises(ExplanationValidationError):
        validate_response(response(claim), packet())


def test_unknown_sentence_and_empty_citation_rejected():
    for ids in (["unknown:s1"], []):
        with pytest.raises(ExplanationValidationError):
            validate_response(response(ids=ids), packet())


def test_missing_evidence_uses_allowed_requirement_and_server_route():
    output = response()
    output["missing_evidence"] = [{"requirement_id": "vm0042.soc_measurements", "record_type": "soil_evidence_review",
                                    "explanation": "The sample value is 12.3 tCO2e.", "sentence_ids": ["source:s1"]}]
    result = validate_response(output, packet())
    assert result["missing_evidence"][0]["route"] == "/fields/f/soil-evidence"
    for key, value in (("requirement_id", "vm0042.fake"), ("record_type", "invented")):
        bad = copy.deepcopy(output)
        bad["missing_evidence"][0][key] = value
        with pytest.raises(ExplanationValidationError):
            validate_response(bad, packet())


def test_numeric_limitation_and_conflict_cannot_bypass_validation():
    out = response()
    out["limitations"] = ["Issuance could be 9000 tCO2e."]
    with pytest.raises(ExplanationValidationError):
        validate_response(out, packet())
    out = response()
    out["conflicts"] = [{"description": "The result is 9000 tCO2e.", "sentence_ids": ["source:s1"]}]
    with pytest.raises(ExplanationValidationError):
        validate_response(out, packet())


def test_corrected_original_cannot_be_cited_alone():
    p = packet()
    p["sources"][0].update(superseded_by_correction=True, correction_ids=["correction:c"])
    p["sources"].append({"id": "correction:c", "title": "Correction", "kind": "correction",
        "sentences": [{"id": "correction:c:s1", "text": "Curated correction summary. Status: draft."}]})
    with pytest.raises(ExplanationValidationError, match="correction_context"):
        validate_response(response(), p)
    assert validate_response(response(ids=["source:s1", "correction:c:s1"]), p)["validation"]["passed"]


def test_one_retry_then_success_and_failure_never_returns_partial():
    calls = []
    def once_bad(prompt, data, schema, **kw):
        calls.append(data)
        return response("999 tCO2e." if len(calls) == 1 else "12.3 tCO2e."), {"provider": "test"}
    result = generate_explanation(packet(), "org", generate_fn=once_bad)
    assert result["retry_count"] == 1 and len(calls) == 2
    assert calls[1]["validation_rejections"]
    calls.clear()
    def always_bad(*a, **kw):
        calls.append(1)
        return response("999 tCO2e."), {"provider": "test"}
    with pytest.raises(ExplanationValidationError):
        generate_explanation(packet(), "org", generate_fn=always_bad)
    assert len(calls) == 2


def test_no_previous_version_skips_provider():
    p = packet()
    p.update(call_model=False, deterministic_message="No previous version")
    def forbidden(*a, **kw):
        raise AssertionError("No provider call expected")
    result = generate_explanation(p, "org", generate_fn=forbidden)
    assert result["deterministic_message"] == "No previous version"


def test_fake_returns_real_citations_and_missing_evidence_links(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "fake")
    p = packet()
    p["sources"][0].update(id="readiness:vm0042.soc_measurements", kind="readiness")
    p["sources"][0]["sentences"] = [{"id": "readiness:vm0042.soc_measurements:s1",
        "text": "Requirement vm0042.soc_measurements. Status: missing."}]
    result = generate_explanation(p, "org")
    assert result["citations_resolved"] and result["missing_evidence"][0]["route"]
    assert result["provider"]["provider"] == "fake"
