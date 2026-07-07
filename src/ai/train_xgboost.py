"""CLI entrypoint: trains the XGBoost baseline on the AI dataset."""

from src.ai import evaluate
from src.ai.dataset_builder import load_dataset
from src.ai.feature_engineering import build_features
from src.ai.models import save_model, train_and_evaluate

MODEL_NAME = "xgboost"


def main():
    df = load_dataset()
    if df.empty:
        print("No dataset found. Run `python -m src.ai.dataset_builder` first.")
        return

    X, y = build_features(df)
    result = train_and_evaluate(MODEL_NAME, X, y)
    print(evaluate.summarize(result))

    path = save_model(result)
    print(f"Saved model to {path}")


if __name__ == "__main__":
    main()
