#!/usr/bin/env python3
"""Restore files into a NEW local directory from a trusted product backup.

Does not connect to a database, execute model artifacts, or overwrite files.
Restore the database separately, point ATTACHMENTS_DIR at the resulting objects
folder, and keep application writers stopped until the whole restore is ready.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backup_product import sha256


def inside(base, name):
    result = (base / name).resolve()
    if base not in result.parents:
        raise ValueError("Backup contains an invalid file path")
    return result


def restore(backup, output):
    if (backup / "INCOMPLETE").exists():
        raise ValueError("Backup is incomplete")
    manifest = json.loads((backup / "manifest.json").read_text())
    if manifest.get("schema_version") != "terra-audit-backup-v1":
        raise ValueError("Unsupported backup version")
    database = inside(backup, manifest["database_file"])
    if sha256(database) != manifest["database_sha256"]:
        raise ValueError("Database checksum mismatch")
    paths = []
    for item in manifest["objects"]:
        source = inside(backup, item["backup_file"])
        destination = inside(output, "objects/" + item["storage_key"])
        if sha256(source) != item["sha256"]:
            raise ValueError("Object checksum mismatch")
        paths.append((source, destination))
    for item in manifest.get("legacy_models", []):
        source = inside(backup, item["backup_file"])
        destination = inside(output, item["backup_file"])
        if sha256(source) != item["sha256"]:
            raise ValueError("Legacy model checksum mismatch")
        paths.append((source, destination))
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    (output / "INCOMPLETE").write_text("Restore in progress\n")
    for source, destination in paths:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as src, destination.open("xb") as dst:
            shutil.copyfileobj(src, dst)
    shutil.copyfile(database, output / manifest["database_file"])
    shutil.copyfile(backup / "manifest.json", output / "manifest.json")
    (output / "INCOMPLETE").unlink()
    print(f"Restored files to {output}; database has NOT been imported into a running server.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    restore(args.backup.expanduser().resolve(), args.output.expanduser().resolve())
