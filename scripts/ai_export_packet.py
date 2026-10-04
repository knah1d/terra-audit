#!/usr/bin/env python3
"""Export a deterministic fixture packet without invoking a model.

Use only a prepared fixture database; exports may contain project evidence.
This script reads existing state and never initializes or seeds a database.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", required=True, help="Canonical ID from tests/ai_eval/manifest.json")
    parser.add_argument("--fixture-only", action="store_true", help="Attest that this database contains disposable fixture evidence only")
    args = parser.parse_args()
    if not args.fixture_only:
        parser.error("Use a disposable fixture database and explicitly pass --fixture-only; never export customer evidence")
    spec = json.loads(args.spec.read_text())
    from src.ai.packets import build_packet
    packet = build_packet(spec["org_id"], spec["project_id"], spec["user_id"],
                          spec["action"], spec["field_id"], **spec.get("parameters", {}))
    expected = spec["expected"]
    required = {"must_mention_requirement_ids", "must_not_claim", "expected_missing_record_types"}
    if not required.issubset(expected):
        parser.error("Expected outcomes must explicitly specify all three coverage lists")
    from src.ai.evaluation import validate_case
    catalog = {row["id"]: row for row in json.loads((Path(__file__).resolve().parents[1] / "tests/ai_eval/manifest.json").read_text())["cases"]}
    case = {"case_id": args.case_id, "packet": packet, "expected": expected,
            "provenance": "exported_by_action_builder", "fixture_only": True}
    for key in ("adversarial_source_text", "adversarial_request"):
        if key in spec:
            case[key] = spec[key]
    try:
        validate_case(case, args.case_id, catalog)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(case, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()
