"""Run the external AWD research benchmark offline; never changes Terra Audit credits.

Example:
python scripts/train_external_awd.py --input data/research/train_HC.parquet
    --output data/external_awd_benchmark

Use only trusted, locally downloaded research datasets. No HTTP fetch or
user-uploaded joblib loading occurs in the Terra Audit API.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.ai.ml.external_awd import checksum, save_benchmark, train_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Research feature parquet or CSV")
    parser.add_argument(
        "--output", type=Path, default=Path("data/external_awd_benchmark"),
        help="Local metrics and model bundle destination",
    )
    parser.add_argument("--group-column", help="Stable plot ID if present in dataset")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"Input does not exist: {args.input}")
    if args.input.suffix.lower() == ".parquet":
        try:
            df = pd.read_parquet(args.input)
        except ImportError as exc:
            raise SystemExit("Install pyarrow to read the research parquet: pip install pyarrow") from exc
    elif args.input.suffix.lower() == ".csv":
        df = pd.read_csv(args.input)
    else:
        parser.error("Supported research files: .parquet and .csv")

    bundle, report = train_benchmark(
        df, source_sha256=checksum(args.input),
        group_column=args.group_column, seed=args.seed,
        test_fraction=args.test_fraction,
    )
    save_benchmark(bundle, report, args.output)
    print(f"Research rows: {report['train_rows']} train / {report['test_rows']} test")
    print(f"Split: {report['split_strategy']}")
    print(f"Accuracy: {report['accuracy']:.3f}; AWD F1: {report['f1']['awd']:.3f}")
    print(f"Saved metrics: {args.output / 'metrics.json'}")
    print("WARNING: No Bangladesh field accuracy, drydown-event accuracy or Verra approval is established.")


if __name__ == "__main__":
    main()
