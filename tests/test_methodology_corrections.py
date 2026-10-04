"""Step 3: real PDF item coverage, bundle limits and tenant-scoped confirmations.

All writes use a throwaway SQLite database. No model, network or project DB.
"""
import re

import pytest
from sqlalchemy import create_engine, text

from src.persistence import database
from src.methodology import library
from src.methodology import registry
from src.methodology import corrections


@pytest.fixture()
def correction_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'corrections.db'}")
    monkeypatch.setattr(database, "_ENGINE", engine)
    with engine.begin() as conn:
        registry.initialize_tables(conn)
        library.initialize_tables(conn)
        conn.execute(text("""CREATE TABLE users (
            user_id TEXT PRIMARY KEY, org_id TEXT, role TEXT, is_active INTEGER DEFAULT 1)"""))
        conn.execute(text("""INSERT INTO users (user_id, org_id, role) VALUES
            ('admin-a', 'org-a', 'admin'), ('admin-b', 'org-b', 'admin'),
            ('viewer-a', 'org-a', 'viewer')"""))
    yield engine
    engine.dispose()


@pytest.fixture()
def indexed(correction_db):
    for doc in registry.list_documents():
        if doc["document_id"] in {
            "vm0042-v2.2", "vm0042-cc-2026-06-11", "vt0014-v1.0", "vt0014-cc-2025-10-16",
        }:
            assert library.ingest_document(doc)["status"] == "indexed"
    return correction_db


def test_every_pdf_item_has_one_manifest_row(correction_db):
    for doc_id, expected in (("vm0042-cc-2026-06-11", 12), ("vt0014-cc-2025-10-16", 3)):
        doc = next(d for d in registry.list_documents() if d["document_id"] == doc_id)
        pages = library._extract_pages(registry.METHODOLOGIES_DIR / doc["file_path"])
        items = [int(m.group(1)) for page in pages for m in corrections._ITEM_HEADING.finditer(page)]
        links = library.list_corrections(doc_id)
        assert items == [r["item_number"] for r in links] == list(range(1, expected + 1))
        assert all(r["status"] == "draft" and r["label"] == "unconfirmed" for r in links)
        for row in links:
            heading = re.compile(rf"^\s*{row['item_number']}\s+{row['item_label']}\s*$", re.I | re.M)
            assert heading.search(pages[row["correction_page"] - 1])


def test_all_items_have_complete_excerpts_without_adjacent_items(indexed):
    for link in corrections.CORRECTION_LINKS:
        retrieved = library.corrections_for(link["target_document_id"], link["target_section"],
                                            link["target_equations"])
        item = next(r for r in retrieved if r["id"] == link["id"])
        assert item["retrieval_status"] == "available", item
        headings = [int(m.group(1)) for c in item["chunks"]
                    for m in corrections._ITEM_HEADING.finditer(c["content"])]
        assert headings == [link["item_number"]]
        assert all(not c["verbatim_quote_safe"] for c in item["chunks"])


def test_reference_search_and_appendix_attach_corrections(indexed):
    bundle = [d["document_id"] for d in registry.get_bundle("vm0042-2026-06")["documents"]]
    rows = library.chunks_for_reference("vm0042-v2.2", "§8.x", document_ids=bundle)
    assert rows and all(r["superseded_by_correction"] for r in rows)
    ids = {c["item_number"] for r in rows for c in r["corrections"]}
    assert set(range(6, 13)) <= ids
    # The reference-level links survive truncating the number of original chunks.
    one = library.chunks_for_reference("vm0042-v2.2", "§8.5 Eq. 39", limit=1, document_ids=bundle)
    assert any(c["item_number"] == 11 for c in one[0]["corrections"])
    # VT0014 is registered, but deliberately not in the current ALM bundle.
    assert library.chunks_for_reference("vt0014-v1.0", "Appendix 4", document_ids=bundle) == []
    appendix = library.chunks_for_reference("vt0014-v1.0", "Appendix 4",
                                            document_ids=["vt0014-v1.0", "vt0014-cc-2025-10-16"])
    assert appendix and any(c["item_number"] == 3 for r in appendix for c in r["corrections"])
    results = library.search("volatile solids", bundle, limit=25)
    affected = [r for r in results if r["document_id"] == "vm0042-v2.2" and r["section"] == "8.2.7"]
    assert affected and all(r["superseded_by_correction"] for r in affected)


def test_bundle_boundary_and_missing_correction_text(indexed):
    assert not library.chunks_for_reference("vm0042-v2.2", "§8.5", document_ids=["vm0051-v1.1"])
    rows = library.chunks_for_reference("vm0042-v2.2", "§8.5", document_ids=["vm0042-v2.2"])
    assert rows and all(not r["original_text_usable_alone"] for r in rows)
    assert all(c["retrieval_status"] == "outside_bundle" and c["chunks"] == []
               for r in rows for c in r["corrections"])
    with database.get_db_connection() as conn:
        conn.execute(text("DELETE FROM methodology_chunks WHERE document_id = 'vm0042-cc-2026-06-11'"))
        conn.commit()
    missing = library.corrections_for("vm0042-v2.2", "8.5")
    assert missing[0]["retrieval_status"] == "not_indexed" and missing[0]["chunks"] == []


def test_confirmation_is_org_scoped_idempotent_and_survives_restart(correction_db):
    link = corrections.CORRECTION_LINKS[0]["id"]
    confirmed = library.confirm_correction(link, "org-a", "admin-a")
    assert confirmed["status"] == "confirmed" and confirmed["curated_by"] == "admin-a"
    assert library.confirm_correction(link, "org-a", "admin-a") == confirmed
    with database.get_db_connection() as conn:
        library.initialize_tables(conn)
        conn.commit()
    assert library.list_corrections(org_id="org-a")[0] == confirmed
    other = library.list_corrections(org_id="org-b")[0]
    assert other["status"] == "draft" and other["curated_by"] is None and other["confirmed_at"] is None
    assert library.list_corrections()[0]["status"] == "draft"
    with pytest.raises(PermissionError):
        library.confirm_correction(link, "org-a", "admin-b")
    with pytest.raises(PermissionError):
        library.confirm_correction(link, "org-a", "viewer-a")


def test_changed_document_invalidates_confirmation_and_index(indexed):
    link = corrections.CORRECTION_LINKS[0]["id"]
    library.confirm_correction(link, "org-a", "admin-a")
    with database.get_db_connection() as conn:
        conn.execute(text("UPDATE methodology_documents SET sha256 = 'changed' "
                          "WHERE document_id = 'vm0042-cc-2026-06-11'"))
        conn.commit()
    stale = library.corrections_for("vm0042-v2.2", "6", org_id="org-a")[0]
    assert stale["confirmation_stale"] and stale["status"] == "draft"
    assert stale["retrieval_status"] == "stale_index" and stale["chunks"] == []


def test_changed_mapping_invalidates_confirmation(correction_db):
    link = corrections.CORRECTION_LINKS[0]["id"]
    library.confirm_correction(link, "org-a", "admin-a")
    with database.get_db_connection() as conn:
        conn.execute(text("UPDATE methodology_correction_links SET target_section = '7' WHERE id = :id"), {"id": link})
        conn.commit()
    stale = library.list_corrections(org_id="org-a")[0]
    assert stale["confirmation_stale"] and stale["status"] == "draft"


def test_index_upgrade_is_additive_and_reingestion_idempotent(indexed):
    doc = next(d for d in registry.list_documents() if d["document_id"] == "vt0014-v1.0")
    assert library.ingest_document(doc)["status"] == "unchanged"
    with database.get_db_connection() as conn:
        conn.execute(text("UPDATE methodology_chunks SET index_version = 1 WHERE document_id = :doc"),
                     {"doc": doc["document_id"]})
        conn.commit()
    assert library.ingest_document(doc)["status"] == "indexed"
    assert library.ingest_document(doc)["status"] == "unchanged"


def test_correction_endpoints_require_admin_and_isolate_confirmations(correction_db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.deps import get_current_user
    from backend.routers.methodology import router

    app = FastAPI()
    app.include_router(router)
    caller = {"org_id": "org-a", "user_id": "viewer-a", "role": "viewer"}
    app.dependency_overrides[get_current_user] = lambda: caller
    with TestClient(app) as client:
        link = corrections.CORRECTION_LINKS[0]["id"]
        assert client.get("/methodology/corrections").status_code == 200
        assert client.post(f"/methodology/corrections/{link}/confirm").status_code == 403
        caller.update(user_id="admin-a", role="admin")
        response = client.post(f"/methodology/corrections/{link}/confirm")
        assert response.status_code == 200 and response.json()["status"] == "confirmed"
        caller.update(org_id="org-b", user_id="admin-b")
        assert client.get("/methodology/corrections").json()[0]["status"] == "draft"
        assert client.post("/methodology/corrections/missing/confirm").status_code == 404
        assert client.get("/methodology/corrections?document_id=missing").status_code == 404
