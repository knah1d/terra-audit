#!/usr/bin/env python3
"""Index registered local PDFs into the configured shared database, without a worker.

This writes reference chunks only; it does not change calculations or readiness.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true", help="Index all registered local PDFs")
    selection.add_argument("--document-id", action="append", help="Registered document ID; repeat as needed")
    args = parser.parse_args()
    from src.persistence.database import get_db_connection
    from src.methodology.library import initialize_tables, ingest_document
    from src.methodology.registry import list_documents
    documents = list_documents()
    if args.document_id:
        unknown = set(args.document_id) - {d["document_id"] for d in documents}
        if unknown:
            parser.error("Unknown registered document IDs: " + ", ".join(sorted(unknown)))
        documents = [d for d in documents if d["document_id"] in args.document_id]
    with get_db_connection() as conn:
        initialize_tables(conn)
        conn.commit()
    failed = False
    for document in documents:
        try:
            result = ingest_document(document)
            failed |= result["status"] == "skipped_no_local_file" and bool(document.get("file_path"))
        except (RuntimeError, ValueError) as exc:
            result = {"document_id": document["document_id"], "status": "error", "error": str(exc)}
            failed = True
        print(json.dumps(result), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
