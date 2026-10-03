#!/usr/bin/env python3
"""Explicit, offline-packet evaluation. Never runs automatically on startup."""
import argparse
import csv
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["self_hosted", "openai", "fake"], required=True)
    parser.add_argument("--cases", type=Path, default=Path("tests/ai_eval/cases"))
    parser.add_argument("--output", type=Path, default=Path("tests/ai_eval/results"))
    args = parser.parse_args()
    os.environ["AI_PROVIDER"] = args.provider
    from src.ai.validate import generate_explanation, ExplanationValidationError, FORBIDDEN_CLAIMS
    from src.ai.providers import generate
    import re
    files = sorted(args.cases.glob("*.json"))
    if not files:
        parser.error("No frozen cases found. Export fixture packets first; no results can be claimed.")
    rows = []
    for path in files:
        case = json.loads(path.read_text())
        packet = case["packet"]
        expected = case["expected"]
        started = time.perf_counter()
        row = {"case": path.stem, "json_valid": False, "validation_passed": False,
               "retry_count": None, "expected_id_coverage": False, "missing_record_coverage": False,
               "forbidden_claims": False, "unknown_citations": False, "error": ""}
        attempts = []
        supplied = {s["id"] for source in packet["sources"] for s in source["sentences"]}
        def observed_generate(*values, **kwargs):
            try:
                response, metadata = generate(*values, **kwargs)
            except ValueError as exc:
                if "invalid response" in str(exc).lower() or "invalid structured response" in str(exc).lower():
                    attempts.append({"json_valid": False, "forbidden": False, "unknown": False})
                raise
            prose = json.dumps(response)
            ids = [sid for group in ("summary_claims", "missing_evidence", "conflicts")
                   for claim in response.get(group, []) if isinstance(claim, dict)
                   for sid in claim.get("sentence_ids", [])]
            attempts.append({"json_valid": isinstance(response, dict),
                "forbidden": any(re.search(pattern, prose, re.I) for pattern in FORBIDDEN_CLAIMS),
                "unknown": any(sid not in supplied for sid in ids)})
            return response, metadata
        try:
            result = generate_explanation(packet, packet["org_id"], generate_fn=observed_generate)
            row.update(json_valid=True, validation_passed=True, retry_count=result["retry_count"])
            # Requirement coverage must be present in returned claim text or
            # structured missing evidence, not merely in supplied packet facts.
            text = json.dumps({k: result[k] for k in ("summary_claims", "missing_evidence", "conflicts", "limitations")})
            row["expected_id_coverage"] = all(r in text for r in expected.get("must_mention_requirement_ids", []))
            types = {r["record_type"] for r in result["missing_evidence"]}
            row["missing_record_coverage"] = set(expected.get("expected_missing_record_types", [])).issubset(types)
            row["forbidden_claims"] = any(word.casefold() in text.casefold() for word in expected.get("must_not_claim", []))
            supplied = {s["id"] for source in packet["sources"] for s in source["sentences"]}
            row["unknown_citations"] = any(c["sentence_id"] not in supplied for c in result["citations_resolved"])
        except ExplanationValidationError as exc:
            row["json_valid"] = not any(check.startswith("schema:") for check in exc.failed_checks)
            row["error"] = str(exc)
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        if attempts:
            row["json_valid"] = all(a["json_valid"] for a in attempts)
            row["forbidden_claims"] = row["forbidden_claims"] or any(a["forbidden"] for a in attempts)
            row["unknown_citations"] = row["unknown_citations"] or any(a["unknown"] for a in attempts)
        row["latency_seconds"] = round(time.perf_counter() - started, 4)
        row["passed"] = (row["json_valid"] and row["validation_passed"] and row["expected_id_coverage"]
                         and row["missing_record_coverage"] and not row["forbidden_claims"] and not row["unknown_citations"])
        rows.append(row)
        print(f"{path.stem}: {'PASS' if row['passed'] else 'FAIL'}")
    latencies = sorted(r["latency_seconds"] for r in rows)
    def percentile(p):
        import math
        return latencies[max(0, math.ceil(len(latencies) * p) - 1)]
    summary = {"provider": args.provider, "cases": len(rows), "passed": sum(r["passed"] for r in rows),
               "json_valid_rate": sum(r["json_valid"] for r in rows) / len(rows),
               "validation_rate": sum(r["validation_passed"] for r in rows) / len(rows),
               "forbidden_claim_cases": sum(r["forbidden_claims"] for r in rows),
               "unknown_citation_cases": sum(r["unknown_citations"] for r in rows),
               "p50_seconds": percentile(.5), "p95_seconds": percentile(.95),
               "note": "Latency includes retries. Rejected outputs are never returned; review per-case failures."}
    summary["minimum_quality_met"] = (len(rows) == 20 and all(r["json_valid"] for r in rows)
        and sum(r["passed"] for r in rows) / len(rows) >= .9
        and not any(r["forbidden_claims"] or r["unknown_citations"] for r in rows))
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / f"{args.provider}.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    (args.output / f"{args.provider}.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if summary["minimum_quality_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
