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


def handle_explanation(job, ctx):
    from src.ai.explanations import packet_for
    from src.ai.validate import generate_explanation
    from src.ai.timing import StageTimings
    from src.ai.packets import evidence_fingerprint
    from src.ai.providers import explanation_signature
    timings = StageTimings("worker", job["job_id"])
    org, payload = job["org_id"], job["payload"]
    project = payload["project_id"]

    def checkpoint():
        if ctx.cancel_requested():
            raise JobCancelled("AI explanation cancelled before publication")
        packet = packet_for(org, project, payload["requested_by"], payload["request"])
        if payload.get("generation_signature") != packet["generation_signature"]:
            raise ValueError("AI provider configuration changed; request a new explanation")
        if (packet["context_sha256"] != payload["context_sha256"] or
                packet["evidence_fingerprint"] != payload["evidence_fingerprint"]):
            raise ValueError("Evidence changed; request a new explanation")
        return packet

    def final_checkpoint():
        if ctx.cancel_requested():
            raise JobCancelled("AI explanation cancelled before publication")
        if explanation_signature() != payload.get("generation_signature"):
            raise ValueError("AI provider configuration changed; request a new explanation")
        # Re-read every fingerprinted value and live access, without repeating
        # readiness calculation, citation retrieval and sentence construction.
        if evidence_fingerprint(org, project, payload["requested_by"], payload["request"]["field_id"]) != payload["evidence_fingerprint"]:
            raise ValueError("Evidence changed; request a new explanation")

    try:
        with timings.measure("initial_packet_and_checkpoint"):
            packet = checkpoint()
        with timings.measure("existing_record_lookup"):
            try:
                ws.get_entry(org, project, job["job_id"], "explanation")
            except ValueError:
                existing = False
            else:
                existing = True
        if existing:
            return {"record_id": job["job_id"]}
        with timings.measure("generation_and_validation"):
            output = generate_explanation(packet, org)
        with timings.measure("final_evidence_and_authorization_check"):
            final_checkpoint()
        output.update(action=packet["action"], field_id=packet["field_id"],
                      generation_signature=packet["generation_signature"],
                      evidence_fingerprint=packet["evidence_fingerprint"],
                      requested_by=payload["requested_by"],
                      calculation_id=payload["request"].get("calculation_id"),
                      assessment_id=payload["request"].get("assessment_id"))
        output["worker_timings_seconds"] = timings.snapshot()
        with timings.measure("save"):
            ws.append(org, project, "explanation", output, job["job_id"])
        return {"record_id": job["job_id"], "worker_timings_seconds": timings.snapshot()}
    except (ValueError, PermissionError, FileNotFoundError, TypeError) as exc:
        raise InvalidJobRequest(str(exc)) from exc
