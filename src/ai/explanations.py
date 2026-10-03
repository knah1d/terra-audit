"""Read-only explanation orchestration using the existing durable record store."""
from src.ai import workspace as ws
from src.ai.packets import build_packet


def packet_for(org_id, project_id, user_id, request):
    params = {k: v for k, v in request.items() if k not in {"action", "field_id"} and v is not None}
    if request["action"] == "missing_evidence":
        params.setdefault("season_ids", [])
    return build_packet(org_id, project_id, user_id, request["action"], request["field_id"], **params)


def cached(org_id, project_id, packet):
    for row in ws.entries(org_id, project_id, "explanation"):
        payload = row["payload"]
        if (payload.get("context_sha256") == packet["context_sha256"] and
                payload.get("evidence_fingerprint") == packet["evidence_fingerprint"] and
                payload.get("action") == packet["action"] and
                payload.get("field_id") == packet["field_id"]):
            return row
    return None
