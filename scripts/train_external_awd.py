"""Run the external AWD research benchmark offline; never changes Terra Audit credits.

Example (AWD task, handcrafted features, Jun 1 – Sep 5 window — chosen over
May 1 – Dec 15 by repeated nested cross-validation; pass that search's JSON
summary with --model-selection to record it):
python scripts/train_external_awd.py \
    --input <ricemapper>/data/features/06-01_09-05_f4d/train_HC.parquet

Use only trusted, locally downloaded research datasets. No HTTP fetch or
user-uploaded joblib loading occurs in the Terra Audit API.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.ai.ml.external_awd import ARTIFACT_DIR, checksum, save_benchmark, train_benchmark
from src.ai.ml.ricemapper_features import feature_names


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Research feature parquet or CSV")
    parser.add_argument(
        "--output", type=Path, default=ARTIFACT_DIR,
        help="Local metrics and model bundle destination",
    )
    parser.add_argument("--group-column", help="Stable plot ID if present in dataset")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-selection", type=Path,
                        help="JSON summary of the window/hyperparameter search to record in metrics")
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
    if set(report["feature_names"]) != set(feature_names()):
        raise SystemExit("Input features differ from the Ricemapper HC features Terra Audit computes "
                         "at inference; use the published train_HC.parquet.")
    report["source_file"] = f"{args.input.parent.name}/{args.input.name}"
    if args.model_selection:
        import json
        report["model_selection"] = json.loads(args.model_selection.read_text(encoding="utf-8"))
    save_benchmark(bundle, report, args.output)
    print(f"Rows (AWD+PTR): {report['rows_awd_ptr']}; duplicates removed: {report['duplicate_rows_removed']}")
    print(f"Research rows: {report['train_rows']} train / {report['test_rows']} test")
    print(f"Split: {report['split_strategy']}")
    cv = report["repeated_cv_5x5"]
    print(f"Repeated 5x5 CV: accuracy {cv['accuracy_mean']:.3f} ± {cv['accuracy_std']:.3f}, "
          f"ROC-AUC {cv['roc_auc_mean']:.3f} ± {cv['roc_auc_std']:.3f}")
    print(f"Test accuracy: {report['accuracy']:.3f}; balanced accuracy: {report['balanced_accuracy']:.3f}")
    for cls in ("not_awd", "awd"):
        print(f"  {'PTR' if cls == 'not_awd' else 'AWD'}: precision {report['precision'][cls]:.3f}, "
              f"recall {report['recall'][cls]:.3f}, F1 {report['f1'][cls]:.3f}, support {report['support'][cls]}")
    print(f"ROC-AUC: {report['roc_auc']:.3f}; Brier: {report['brier_score']:.3f}")
    print(f"Confusion matrix (rows actual PTR, AWD; cols predicted): {report['confusion_matrix']}")
    print(f"Saved metrics: {args.output / 'metrics.json'}")
    print("WARNING: No Bangladesh field accuracy, drydown-event accuracy or Verra approval is established.")


if __name__ == "__main__":
    main()
