"""CLI entrypoint: trains the Random Forest baseline on the AI dataset."""

from src.ai import evaluate
from src.ai.dataset_builder import load_dataset
from src.ai.feature_engineering import build_features
from src.ai.models import save_model, train_and_evaluate

MODEL_NAME = "random_forest"


def main(org_id="default"):
    df = load_dataset(org_id)
    if df.empty:
        print("No dataset found. Run `python -m src.ai.dataset_builder` first.")
        return

    X, y = build_features(df)
    result = train_and_evaluate(MODEL_NAME, X, y)
    print(evaluate.summarize(result))

    result["model_name"] = f"{org_id}_{MODEL_NAME}"
    path = save_model(result)
    print(f"Saved model to {path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org-id", default="default")
    main(parser.parse_args().org_id)
