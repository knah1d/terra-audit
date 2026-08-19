from pydantic import BaseModel


class DatasetBuildResult(BaseModel):
    row_count: int
    field_window_groups: int
    label_counts: dict[str, int]


class TrainRequest(BaseModel):
    model_key: str = "random_forest"  # "random_forest" | "xgboost"
    k: int = 3


class TrainAccepted(BaseModel):
    job_id: str
