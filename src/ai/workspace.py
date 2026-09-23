"""Project-scoped immutable AI records and audited deployment selection."""
import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import text
from src.database import get_db_connection
from src.monitoring import digest
from src.projects import get_project, get_project_member, list_project_fields

KINDS = {"model", "prediction", "answer", "document", "document_review", "deployment"}


def initialize_tables(conn):
    conn.execute(text("""CREATE TABLE IF NOT EXISTS ai_records (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, project_id TEXT NOT NULL,
        kind TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)"""))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ai_scope ON ai_records(org_id,project_id,kind)"))
    conn.execute(text("""CREATE TABLE IF NOT EXISTS ai_deployments (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL, revision INTEGER NOT NULL,
        model_id TEXT, threshold REAL NOT NULL, PRIMARY KEY(org_id,project_id))"""))


def active_fields(org_id, project_id):
    today = date.today().isoformat()
    return {r["field_id"] for r in list_project_fields(org_id, project_id)
            if not r["removed_at"] and r["effective_start_date"] <= today
            and (not r["effective_end_date"] or r["effective_end_date"] >= today)}


def authorize(org_id, project_id, user_id, lead=False):
    """Re-check live identity and membership, including inside queued jobs."""
    with get_db_connection() as conn:
        row = conn.execute(text("SELECT user_id,org_id,role FROM users WHERE user_id=:u AND org_id=:o AND is_active=1"),
                           {"u": user_id, "o": org_id}).mappings().first()
    if not row or not get_project(org_id, project_id):
        raise PermissionError("Project is unavailable to this account")
    member = get_project_member(org_id, project_id, user_id)
    if row["role"] != "admin" and (not member or (lead and member["project_role"] != "lead")):
        raise PermissionError("Project lead access required" if lead else "Project membership required")
    if lead and row["role"] not in {"admin", "analyst"}:
        raise PermissionError("A writer role is required")
    return dict(row)


def entries(org_id, project_id, kind=None):
    query = "SELECT * FROM ai_records WHERE org_id=:o AND project_id=:p"
    args = {"o": org_id, "p": project_id}
    if kind:
        query += " AND kind=:k"
        args["k"] = kind
    with get_db_connection() as conn:
        rows = conn.execute(text(query + " ORDER BY created_at DESC,id DESC"), args).mappings().all()
    return [{**r, "payload": json.loads(r["payload"])} for r in rows]


def get_entry(org_id, project_id, record_id, kind=None):
    with get_db_connection() as conn:
        r = conn.execute(text("SELECT * FROM ai_records WHERE org_id=:o AND project_id=:p AND id=:i"),
                         {"o": org_id, "p": project_id, "i": record_id}).mappings().first()
    if not r or (kind and r["kind"] != kind):
        raise ValueError("AI record not found in this project")
    return {**r, "payload": json.loads(r["payload"])}


def append(org_id, project_id, kind, payload, record_id=None, conn=None):
    if kind not in KINDS:
        raise ValueError("Unknown AI record type")
    rid = record_id or uuid.uuid4().hex
    values = dict(id=rid, org_id=org_id, project_id=project_id, kind=kind,
                  created_at=datetime.now(timezone.utc).isoformat(),
                  payload=json.dumps(payload, sort_keys=True, allow_nan=False, default=str))
    sql = text("""INSERT INTO ai_records(id,org_id,project_id,kind,created_at,payload)
        VALUES (:id,:org_id,:project_id,:kind,:created_at,:payload) ON CONFLICT(id) DO NOTHING""")
    if conn is not None:
        conn.execute(sql, values)
    else:
        with get_db_connection() as db:
            db.execute(sql, values)
            db.commit()
    return rid


def deployment(org_id, project_id):
    with get_db_connection() as conn:
        r = conn.execute(text("SELECT revision,model_id,threshold FROM ai_deployments WHERE org_id=:o AND project_id=:p"),
                         {"o": org_id, "p": project_id}).mappings().first()
    return dict(r) if r else {"revision": 0, "model_id": None, "threshold": 0.8}


def set_deployment(org_id, project_id, model_id, threshold, expected_revision, actor, reason):
    if model_id:
        model = get_entry(org_id, project_id, model_id, "model")["payload"]
        if not model.get("evaluation", {}).get("models"):
            raise ValueError("A completed held-out evaluation is required")
    args = dict(o=org_id, p=project_id, m=model_id, t=threshold, r=expected_revision)
    with get_db_connection() as conn:
        conn.execute(text("""INSERT INTO ai_deployments(org_id,project_id,revision,model_id,threshold)
            VALUES (:o,:p,0,NULL,0.8) ON CONFLICT(org_id,project_id) DO NOTHING"""), args)
        changed = conn.execute(text("""UPDATE ai_deployments SET revision=revision+1,model_id=:m,threshold=:t
            WHERE org_id=:o AND project_id=:p AND revision=:r"""), args)
        if changed.rowcount != 1:
            raise ValueError("Deployment changed in another session; refresh before trying again")
        append(org_id, project_id, "deployment", {"model_id": model_id, "threshold": threshold,
               "revision": expected_revision + 1, "actor": actor, "reason": reason}, conn=conn)
        conn.commit()
    return deployment(org_id, project_id)


def frozen_corpus(org_id, project_id):
    from src.ai.crop_benchmark import build_corpus
    corpus = build_corpus(org_id, active_fields(org_id, project_id))
    corpus.pop("sha256", None)
    corpus["project_id"] = project_id
    return {**corpus, "sha256": digest(corpus)}
