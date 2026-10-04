#!/usr/bin/env python3
"""Evaluate frozen fixture packets explicitly; never runs on app startup."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["self_hosted", "groq", "openai", "fake"], required=True)
    parser.add_argument("--cases", type=Path, default=ROOT / "tests/ai_eval/cases")
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests/ai_eval/manifest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "tests/ai_eval/results")
    parser.add_argument("--preflight-only", action="store_true", help="Check all 20 fixtures without calling any provider")
    args = parser.parse_args()
    from src.ai.evaluation import load_suite, requirement_coverage
    try:
        cases = load_suite(args.cases, args.manifest)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(f"Fixture preflight failed: {exc}")
    if args.preflight_only:
        print("20 canonical builder-exported fixture packets accepted. No provider called; no quality result claimed.")
        return 0
    os.environ["AI_PROVIDER"] = args.provider
    from src.ai.validate import generate_explanation, ExplanationValidationError, FORBIDDEN_CLAIMS
    from src.ai.providers import generate, explanation_signature, provider_status
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + args.provider + "-" + uuid.uuid4().hex[:8]
    destination = args.output / run_id
    destination.mkdir(parents=True, exist_ok=False)
    rows, artifacts, review = [], [], []
    for case_id, case, catalog in cases:
        packet, expected = case["packet"], case["expected"]
        started = time.perf_counter()
        row = {"case": case_id, "category": catalog["category"], "context_sha256": packet["context_sha256"],
               "json_valid": False, "validation_passed": False, "retry_count": None, "provider_attempts": 0,
               "expected_id_coverage": False, "missing_record_coverage": False,
               "forbidden_claims": False, "unknown_citations": False, "failed_checks": "", "error": ""}
        attempts = []
        supplied = {s["id"] for source in packet["sources"] for s in source["sentences"]}

        def observed_generate(*values, **kwargs):
            if case.get("adversarial_request"):
                # Evaluation-only hostile request; the exported packet is never edited.
                values = (values[0], {**values[1], "user_request": case["adversarial_request"]}, *values[2:])
            try:
                response, metadata = generate(*values, **kwargs)
            except ValueError as exc:
                if "invalid response" in str(exc).lower() or "invalid structured response" in str(exc).lower():
                    attempts.append({"json_valid": False, "forbidden": False, "unknown": False})
                raise
            ids = [sid for group in ("summary_claims", "missing_evidence", "conflicts")
                   for claim in response.get(group, []) if isinstance(claim, dict)
                   for sid in claim.get("sentence_ids", [])]
            prose = json.dumps(response)
            attempts.append({"json_valid": isinstance(response, dict),
                             "forbidden": any(re.search(pattern, prose, re.I) for pattern in FORBIDDEN_CLAIMS)
                             or any(word.casefold() in prose.casefold() for word in expected["must_not_claim"]),
                             "unknown": any(sid not in supplied for sid in ids)})
            return response, metadata

        result = None
        try:
            result = generate_explanation(packet, packet["org_id"], generate_fn=observed_generate)
            row.update(json_valid=True, validation_passed=True, retry_count=result["retry_count"])
            row["expected_id_coverage"] = requirement_coverage(result, expected["must_mention_requirement_ids"])
            types = {r["record_type"] for r in result["missing_evidence"]}
            row["missing_record_coverage"] = set(expected["expected_missing_record_types"]).issubset(types)
            prose = json.dumps({k: result[k] for k in ("summary_claims", "missing_evidence", "conflicts", "limitations")})
            row["forbidden_claims"] = any(word.casefold() in prose.casefold() for word in expected["must_not_claim"])
            row["unknown_citations"] = any(c["sentence_id"] not in supplied for c in result["citations_resolved"])
        except ExplanationValidationError as exc:
            row["json_valid"] = bool(attempts) and all(a["json_valid"] for a in attempts)
            row["failed_checks"] = "; ".join(exc.failed_checks)
            row["error"] = str(exc)
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        if attempts:
            row["json_valid"] = all(a["json_valid"] for a in attempts)
            row["forbidden_claims"] |= any(a["forbidden"] for a in attempts)
            row["unknown_citations"] |= any(a["unknown"] for a in attempts)
        row["provider_attempts"] = len(attempts)
        if row["retry_count"] is None and attempts:
            row["retry_count"] = len(attempts) - 1
        row["latency_seconds"] = round(time.perf_counter() - started, 4)
        row["passed"] = (row["json_valid"] and row["validation_passed"] and row["expected_id_coverage"]
                         and row["missing_record_coverage"] and not row["forbidden_claims"] and not row["unknown_citations"])
        rows.append(row)
        output_hash = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        artifacts.append({"case": case_id, "context_sha256": packet["context_sha256"], "output_sha256": output_hash,
                          "result": result, "metrics": row})
        review.append({"case": case_id, "context_sha256": packet["context_sha256"], "output_sha256": output_hash,
                       "claims_supported": None, "actions_correct": None, "qualifications_correct": None, "notes": ""})
        # Persist completed cases, even if a later case is interrupted.
        (destination / "outputs.json").write_text(json.dumps(artifacts, indent=2, ensure_ascii=False) + "\n")
        print(f"{case_id}: {'PASS' if row['passed'] else 'FAIL'}")
    latencies = sorted(r["latency_seconds"] for r in rows)
    provider_latencies = sorted(r["latency_seconds"] for r in rows if r["provider_attempts"])
    def percentile(values, p):
        return values[max(0, math.ceil(len(values) * p) - 1)] if values else None
    structural = (all(r["json_valid"] for r in rows) and sum(r["passed"] for r in rows) / len(rows) >= .9
                  and not any(r["forbidden_claims"] or r["unknown_citations"] for r in rows))
    summary = {"run_id": run_id, "provider": args.provider, "model": provider_status()["model"],
               "generation_signature": explanation_signature(), "cases": len(rows), "passed": sum(r["passed"] for r in rows),
               "json_valid_rate": sum(r["json_valid"] for r in rows) / len(rows),
               "validation_rate": sum(r["validation_passed"] for r in rows) / len(rows),
               "forbidden_claim_cases": sum(r["forbidden_claims"] for r in rows),
               "unknown_citation_cases": sum(r["unknown_citations"] for r in rows),
               "p50_seconds": percentile(latencies, .5), "p95_seconds": percentile(latencies, .95),
               "provider_cases": len(provider_latencies), "provider_p50_seconds": percentile(provider_latencies, .5),
               "provider_p95_seconds": percentile(provider_latencies, .95), "structural_threshold_met": structural,
               "minimum_quality_met": False, "human_review_completed": False, "release_candidate": False,
               "note": "Structural metrics do not prove semantic support. Fake proves wiring only. Latency includes retries; no deployment/provider enablement is changed."}
    with (destination / "cases.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (destination / "review-template.json").write_text(json.dumps({"run_id": run_id, "reviewer": "", "cases": review}, indent=2) + "\n")
    print(json.dumps(summary, indent=2)); print(f"Artifacts: {destination}")
    return 0 if structural else 1


if __name__ == "__main__":
    raise SystemExit(main())
