"""Offline evaluation contracts. No database initialization or model calls."""
import hashlib
import json
import re
from pathlib import Path

EXPECTED_LISTS = ("must_mention_requirement_ids", "must_not_claim", "expected_missing_record_types")


def packet_hash(packet: dict) -> str:
    from src.ai.packets import canonical_json
    return hashlib.sha256(canonical_json({k: v for k, v in packet.items() if k != "context_sha256"}).encode()).hexdigest()


def validate_case(case: dict, case_id: str, catalog: dict) -> None:
    """Reject malformed/tampered fixtures before spending provider tokens."""
    if case_id not in catalog:
        raise ValueError(f"Unknown evaluation case: {case_id}")
    if case.get("provenance") != "exported_by_action_builder" or case.get("fixture_only") is not True:
        raise ValueError(f"{case_id}: require a builder-exported, explicitly fixture-only packet")
    packet = case.get("packet")
    expected = case.get("expected")
    if not isinstance(packet, dict) or not isinstance(expected, dict):
        raise ValueError(f"{case_id}: packet and expected must be objects")
    if packet.get("action") != catalog[case_id]["action"]:
        raise ValueError(f"{case_id}: wrong action for the coverage manifest")
    if not packet.get("org_id") or not packet.get("evidence_fingerprint"):
        raise ValueError(f"{case_id}: missing organization or evidence fingerprint")
    if packet.get("context_sha256") != packet_hash(packet):
        raise ValueError(f"{case_id}: packet hash mismatch; re-export from fixture state")
    for key in EXPECTED_LISTS:
        if not isinstance(expected.get(key), list) or any(not isinstance(v, str) or not v for v in expected[key]):
            raise ValueError(f"{case_id}: {key} must be an explicit list of nonempty strings")
    allowed = set(packet.get("allowed_requirement_ids", []))
    if not set(expected["must_mention_requirement_ids"]) <= allowed:
        raise ValueError(f"{case_id}: expected requirement was not supplied in the packet")
    if catalog[case_id].get("requires_requirement") and not expected["must_mention_requirement_ids"]:
        raise ValueError(f"{case_id}: requirement coverage must not be empty")
    if catalog[case_id]["category"] == "correction" and not any(source.get("kind") == "correction" for source in packet.get("sources", [])):
        raise ValueError(f"{case_id}: an affected correction source must be present")
    if case_id == "19-document-injection":
        hostile = case.get("adversarial_source_text")
        if not isinstance(hostile, str) or not hostile.strip() or not any(hostile in sentence["text"] for source in packet.get("sources", []) if source.get("kind") == "methodology" for sentence in source["sentences"]):
            raise ValueError(f"{case_id}: declare the hostile text and include it in the fixture methodology before export")
    if case_id == "20-approval-request" and (not isinstance(case.get("adversarial_request"), str) or not case["adversarial_request"].strip()):
        raise ValueError(f"{case_id}: supply the evaluation-only hostile user request")
    if catalog[case_id]["category"] == "adversarial" and not expected["must_not_claim"]:
        raise ValueError(f"{case_id}: specify forbidden output phrases")
    ids = []
    source_ids = []
    for source in packet.get("sources", []):
        source_ids.append(source["id"])
        for sentence in source["sentences"]:
            if not isinstance(sentence.get("text"), str) or not sentence["text"]:
                raise ValueError(f"{case_id}: invalid source sentence")
            ids.append(sentence["id"])
    if len(ids) != len(set(ids)) or len(source_ids) != len(set(source_ids)):
        raise ValueError(f"{case_id}: duplicate source/sentence IDs")
    if catalog[case_id].get("deterministic") and packet.get("call_model", True):
        raise ValueError(f"{case_id}: must exercise the deterministic no-provider path")


def load_suite(directory: Path, manifest: Path):
    catalog_rows = json.loads(manifest.read_text())["cases"]
    catalog = {row["id"]: row for row in catalog_rows}
    if len(catalog) != 20 or len(catalog) != len(catalog_rows):
        raise ValueError("Coverage manifest must contain 20 unique cases")
    cases = []
    seen = set()
    for path in sorted(directory.glob("*.json")):
        case = json.loads(path.read_text())
        case_id = case.get("case_id", path.stem)
        if case_id in seen:
            raise ValueError(f"Duplicate case: {case_id}")
        validate_case(case, case_id, catalog)
        seen.add(case_id)
        cases.append((case_id, case, catalog[case_id]))
    missing = sorted(set(catalog) - seen)
    if missing:
        raise ValueError("Missing canonical cases: " + ", ".join(missing))
    return cases


def requirement_coverage(result: dict, required: list[str]) -> bool:
    prose = "\n".join(row["text"] for row in result.get("summary_claims", []))
    prose += "\n" + "\n".join(row["description"] for row in result.get("conflicts", []))
    structured = {row["requirement_id"] for row in result.get("missing_evidence", [])}
    return all(rid in structured or re.search(r"(?<![\w.])" + re.escape(rid) + r"(?![\w.])", prose) for rid in required)
