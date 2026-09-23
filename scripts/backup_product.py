#!/usr/bin/env python3
"""Offline backup of the database and referenced files; never overwrites output.

Stop ALL API/worker/Streamlit writers before invoking with --writers-stopped.
The flag is an operator assertion, not automatic service control. This command
makes no changes to the application database or object store.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import make_url


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def backup(output):
    from src.database import DB_PATH, get_db_connection
    from src.storage import get_storage
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    os.chmod(output, 0o700)
    (output / "INCOMPLETE").write_text("Only a backup with manifest.json and no INCOMPLETE marker is complete.\n")
    url = make_url(os.environ.get("DATABASE_URL") or f"sqlite:///{DB_PATH}")
    if url.get_backend_name() == "sqlite":
        source = Path(url.database).resolve()
        if not source.is_file():
            raise ValueError("SQLite source is not a file")
        db_file = output / "database.sqlite"
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as conn, sqlite3.connect(db_file) as destination:
            conn.backup(destination)
        database_format = "sqlite"
    elif url.get_backend_name() == "postgresql":
        db_file = output / "database.dump"
        env = {**os.environ, "PGHOST": url.host or "localhost", "PGPORT": str(url.port or 5432),
               "PGDATABASE": url.database or "", "PGUSER": url.username or "", "PGPASSWORD": url.password or ""}
        if url.query.get("sslmode"):
            env["PGSSLMODE"] = url.query["sslmode"]
        result = subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(db_file)],
                                env=env, capture_output=True)
        if result.returncode:
            raise ValueError("pg_dump failed; check PostgreSQL client version, credentials and network access")
        database_format = "postgresql-custom"
    else:
        raise ValueError("Only SQLite and PostgreSQL are supported")
    with get_db_connection() as conn:
        attachments = conn.execute(text("SELECT storage_key,sha256 FROM attachments")).mappings().all()
        model_rows = conn.execute(text("SELECT payload FROM ai_records WHERE kind='model'")).scalars().all()
    objects = {r["storage_key"]: r["sha256"] for r in attachments}
    for raw in model_rows:
        model = json.loads(raw)
        objects[model["artifact_key"]] = model["artifact_sha256"]
    storage = get_storage()
    manifest = {"schema_version": "terra-audit-backup-v1", "created_at": datetime.now(timezone.utc).isoformat(),
                "database_format": database_format, "database_file": db_file.name, "database_sha256": sha256(db_file),
                "objects": [], "legacy_models": [], "writers_stopped_asserted": True}
    for key, expected in sorted(objects.items()):
        filename = "objects/" + hashlib.sha256(key.encode()).hexdigest()
        target = output / filename
        target.parent.mkdir(exist_ok=True)
        with storage.open(key) as source, target.open("xb") as destination:
            shutil.copyfileobj(source, destination, length=1024 * 1024)
        actual = sha256(target)
        if actual != expected:
            raise ValueError("Referenced file checksum mismatch; backup remains INCOMPLETE")
        manifest["objects"].append({"storage_key": key, "backup_file": filename, "sha256": actual})
    legacy = ROOT / "data" / "ai_models"
    if legacy.exists():
        for source in sorted(legacy.rglob("*")):
            if source.is_symlink():
                raise ValueError("Legacy model directory contains a symlink; inspect it before backup")
            if source.is_file():
                relative = Path("legacy_models") / source.relative_to(legacy)
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                manifest["legacy_models"].append({"backup_file": str(relative), "sha256": sha256(target)})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "INCOMPLETE").unlink()
    print(f"Backup saved: {output} ({len(objects)} referenced objects)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="A new directory outside the live data directory")
    parser.add_argument("--writers-stopped", action="store_true", help="Confirm all application writers have been stopped")
    args = parser.parse_args()
    if not args.writers_stopped:
        parser.error("Stop API, worker and Streamlit writers, then pass --writers-stopped")
    load_dotenv(ROOT / ".env")
    target = args.output.expanduser().resolve()
    live_data = (ROOT / "data").resolve()
    live_objects = Path(os.environ.get("ATTACHMENTS_DIR", live_data / "attachments")).resolve()
    if target == live_data or live_data in target.parents or target == live_objects or live_objects in target.parents:
        parser.error("Choose an output directory outside live data and attachment storage")
    try:
        backup(target)
    except Exception as exc:
        # Do not print SQL/SDK exception details containing endpoints or credentials.
        print(f"Backup failed ({type(exc).__name__}); incomplete output is retained. Check configuration and storage access.", file=sys.stderr)
        sys.exit(1)
