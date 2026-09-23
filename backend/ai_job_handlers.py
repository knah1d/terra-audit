"""AI queue handlers with live authorization and cancellation checkpoints."""
from src.ai import workspace as ws
from src.jobs import InvalidJobRequest, JobCancelled
from src.monitoring import season


def handle_workspace(job, ctx):
    org, p = job["org_id"], job["payload"]
    project_id, kind = p["project_id"], job["job_type"].removeprefix("workspace_")

    def checkpoint():
        if ctx.cancel_requested():
            raise JobCancelled("AI job cancelled before publication")
        ws.authorize(org, project_id, p["requested_by"], lead=True)
        if p.get("field_id") and p["field_id"] not in ws.active_fields(org, project_id):
            raise ValueError("Field is no longer active in this project")
        if kind == "prediction":
            current = season(org, p["field_id"], p["season_id"])
            if not current or current["id"] != p["season"]["id"]:
                raise ValueError("Season changed; submit a new prediction request")
            if ws.deployment(org, project_id)["revision"] != p["deployment_revision"]:
                raise ValueError("Active model decision changed; submit a new prediction request")

    try:
        checkpoint()
        if kind == "train":
            from src.ai.managed_models import train
            return train(org, project_id, job["job_id"], p, checkpoint)
        if any(r["id"] == job["job_id"] for r in ws.entries(org, project_id, kind)):
            return {"record_id": job["job_id"]}
        if kind == "prediction":
            from src.ai.managed_models import predict
            output = predict(org, project_id, p)
        elif kind == "answer":
            from src.ai.assistant import answer
            output = answer(org, project_id, p)
        elif kind == "document":
            from src.ai.assistant import document
            output = document(org, project_id, p, checkpoint)
        else:
            raise ValueError("Unknown AI job type")
        checkpoint()
        ws.append(org, project_id, kind, output, job["job_id"])
        return {"record_id": job["job_id"]}
    except (ValueError, PermissionError, FileNotFoundError) as exc:
        raise InvalidJobRequest(str(exc)) from exc
