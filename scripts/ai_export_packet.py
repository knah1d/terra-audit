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
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    from src.ai.packets import build_packet
    packet = build_packet(spec["org_id"], spec["project_id"], spec["user_id"],
                          spec["action"], spec["field_id"], **spec.get("parameters", {}))
    expected = spec["expected"]
    required = {"must_mention_requirement_ids", "must_not_claim", "expected_missing_record_types"}
    if not required.issubset(expected):
        parser.error("Expected outcomes must explicitly specify all three coverage lists")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"packet": packet, "expected": expected,
                                      "provenance": "exported_by_action_builder"}, indent=2, default=str) + "\n")


if __name__ == "__main__":
    main()
