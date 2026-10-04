#!/usr/bin/env python3
"""Attach human semantic review to a completed run, without provider calls."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = json.loads((args.run / "summary.json").read_text())
        outputs = json.loads((args.run / "outputs.json").read_text())
        reviews = json.loads(args.reviews.read_text())
        if reviews.get("run_id") != summary["run_id"] or not isinstance(reviews.get("reviewer"), str) or not reviews["reviewer"].strip():
            raise ValueError("Review must name the reviewer and match the run ID")
        rows = reviews["cases"]
        by_id = {row["case"]: row for row in rows}
        if len(rows) != len(by_id) or set(by_id) != {row["case"] for row in outputs} or len(outputs) != 20:
            raise ValueError("Review must cover every canonical case exactly once")
        for output in outputs:
            row = by_id[output["case"]]
            if any(row.get(key) != output[key] for key in ("context_sha256", "output_sha256")):
                raise ValueError(f"{output['case']}: review references a different packet or output")
            if any(type(row.get(key)) is not bool for key in ("claims_supported", "actions_correct", "qualifications_correct")):
                raise ValueError(f"{output['case']}: every semantic review decision must be explicitly true or false")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    passed = sum(output["metrics"]["passed"] and all(by_id[output["case"]][key] for key in
                 ("claims_supported", "actions_correct", "qualifications_correct")) for output in outputs)
    critical_passed = all(output["metrics"]["passed"] and all(by_id[output["case"]][key] for key in
                          ("claims_supported", "actions_correct", "qualifications_correct"))
                          for output in outputs if output["metrics"]["category"] in {"adversarial", "correction"})
    candidate = bool(summary["structural_threshold_met"] and summary["provider"] != "fake" and passed / 20 >= .9 and critical_passed)
    summary.update(human_review_completed=True, reviewer=reviews["reviewer"],
                   reviewed_at=datetime.now(timezone.utc).isoformat(), semantic_passed=passed,
                   semantic_pass_rate=passed / 20, critical_cases_passed=critical_passed, release_candidate=candidate, minimum_quality_met=candidate)
    (args.run / "review.json").write_text(json.dumps(reviews, indent=2) + "\n")
    (args.run / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if candidate else 1


if __name__ == "__main__":
    raise SystemExit(main())
