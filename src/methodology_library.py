"""Methodology knowledge library — Phase 4A step 1.

Indexes every registered methodology PDF (src.methodology_registry
DOCUMENTS with a local file) into `methodology_chunks`: one row per
(document, page, section segment), carrying the section heading in
force, equation numbers found in that segment, the text, and the source
file's sha256. Retrieval is full-text only (SQLite FTS5 / Postgres
tsvector) — no embeddings.

Text comes from `pdftotext -layout` (poppler-utils). Extraction is
imperfect: equation symbols/subscripts and tables are often garbled, so
equations should be cited by number + page, never quoted for their
values (the calculation engine is the source of numeric results).

Re-ingestion is idempotent per document: if the stored sha256 matches
the file on disk, the document is skipped; otherwise its chunks are
replaced, so a replaced PDF never leaves stale text behind.
"""
import re
import shutil
import subprocess

from sqlalchemy import text

from src.database import get_db_connection, is_sqlite
from src.methodology_corrections import (
    attach_corrections, confirm_correction, corrections_for, list_corrections,
)

_HEADING = re.compile(r"^\s{0,12}(\d{1,2}(?:\.\d{1,2}){0,3})\s{1,8}([A-Z][^\n]{2,120}?)\s*$")
_TOC_LEADER = re.compile(r"\.{4,}\s*\d+\s*$")
_EQUATION = re.compile(r"\((\d{1,3})\)\s*$")
_APPENDIX_HEADING = re.compile(r"^\s{0,12}APPENDIX\s+(\d+)\s*:\s*(.+)$")
MAX_CHUNK_CHARS = 6000
INDEX_VERSION = 2  # Appendix headings are now indexed for correction-aware retrieval.


def initialize_tables(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS methodology_chunks (
            chunk_id        TEXT PRIMARY KEY,
            document_id     TEXT NOT NULL,
            document_sha256 TEXT NOT NULL,
            page            INTEGER NOT NULL,
            segment         INTEGER NOT NULL,
            section         TEXT NOT NULL DEFAULT '',
            section_title   TEXT NOT NULL DEFAULT '',
            equations       TEXT NOT NULL DEFAULT '',
            content         TEXT NOT NULL,
            index_version   INTEGER NOT NULL DEFAULT 1
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_methodology_chunks_doc ON methodology_chunks(document_id, page)"))
    if is_sqlite():
        from sqlalchemy.exc import OperationalError
        try:
            conn.execute(text("ALTER TABLE methodology_chunks ADD COLUMN index_version INTEGER NOT NULL DEFAULT 1"))
        except OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS methodology_chunks_fts
            USING fts5(chunk_id UNINDEXED, section_title, content, tokenize='porter unicode61')
        """))
    else:
        conn.execute(text("ALTER TABLE methodology_chunks ADD COLUMN IF NOT EXISTS index_version INTEGER NOT NULL DEFAULT 1"))
        conn.execute(text(
            "ALTER TABLE methodology_chunks ADD COLUMN IF NOT EXISTS search tsvector "
            "GENERATED ALWAYS AS (to_tsvector('english', section_title || ' ' || content)) STORED"
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_methodology_chunks_search ON methodology_chunks USING GIN (search)"))
    from src.methodology_corrections import initialize_tables as initialize_corrections
    initialize_corrections(conn)


def _extract_pages(pdf_path) -> list[str]:
    if not shutil.which("pdftotext"):
        raise RuntimeError("Methodology indexing requires pdftotext. Install poppler-utils on the worker host.")
    result = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, timeout=300)
    if result.returncode != 0:
        raise ValueError(f"pdftotext failed for {pdf_path}: {result.stderr.decode(errors='replace')[:300]}")
    pages = result.stdout.decode("utf-8", errors="replace").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def _is_heading(number: str, title: str) -> bool:
    """Rejects footnotes ("12 Note that ...", "4 Available at: https://...")
    that share the numbered-line shape: real headings are short, don't end
    in sentence punctuation, and a bare top-level number ("5") only counts
    when its title is ALL CAPS ("5 PROCEDURES")."""
    title = title.strip()
    if len(title) > 90 or title[-1] in ".,;:" or "http" in title:
        return False
    if "." not in number:
        return title.upper() == title
    return True


def _segment_pages(pages: list[str]) -> list[dict]:
    """Splits each page wherever a numbered section heading starts, and
    carries the heading in force across page boundaries."""
    chunks = []
    section, title = "", ""
    for page_no, page in enumerate(pages, start=1):
        current, equations, segment = [], set(), 0

        def flush():
            nonlocal current, equations, segment
            body = "\n".join(current).strip()
            if body:
                for start in range(0, len(body), MAX_CHUNK_CHARS):
                    chunks.append({"page": page_no, "segment": segment, "section": section,
                                   "section_title": title, "equations": ",".join(sorted(equations, key=int)),
                                   "content": body[start:start + MAX_CHUNK_CHARS]})
                    segment += 1
            current, equations = [], set()

        for line in page.splitlines():
            heading = _HEADING.match(line)
            appendix = _APPENDIX_HEADING.match(line)
            if appendix and not _TOC_LEADER.search(line):
                flush()
                section, title = f"Appendix {appendix.group(1)}", appendix.group(2).strip()
            elif heading and not _TOC_LEADER.search(line) and _is_heading(heading.group(1), heading.group(2)):
                flush()
                section, title = heading.group(1), heading.group(2).strip()
            eq = _EQUATION.search(line)
            if eq:
                equations.add(eq.group(1))
            current.append(line.rstrip())
        flush()
    return chunks


def ingest_document(document: dict) -> dict:
    """document: a row from src.methodology_registry.list_documents()."""
    from src.methodology_registry import METHODOLOGIES_DIR, _file_sha256
    doc_id, rel = document["document_id"], document.get("file_path")
    if not rel or not (METHODOLOGIES_DIR / rel).exists():
        return {"document_id": doc_id, "status": "skipped_no_local_file"}
    sha = _file_sha256(rel)
    with get_db_connection() as conn:
        existing = conn.execute(text(
            "SELECT document_sha256, index_version FROM methodology_chunks WHERE document_id = :d LIMIT 1"
        ), {"d": doc_id}).mappings().first()
    if existing and existing["document_sha256"] == sha and existing["index_version"] == INDEX_VERSION:
        return {"document_id": doc_id, "status": "unchanged"}
    chunks = _segment_pages(_extract_pages(METHODOLOGIES_DIR / rel))
    with get_db_connection() as conn:
        if is_sqlite():
            conn.execute(text(
                "DELETE FROM methodology_chunks_fts WHERE chunk_id IN "
                "(SELECT chunk_id FROM methodology_chunks WHERE document_id = :d)"), {"d": doc_id})
        conn.execute(text("DELETE FROM methodology_chunks WHERE document_id = :d"), {"d": doc_id})
        rows = [{**c, "chunk_id": f"{doc_id}:p{c['page']}:c{c['segment']}", "document_id": doc_id,
                 "document_sha256": sha, "index_version": INDEX_VERSION} for c in chunks]
        if rows:
            conn.execute(text("""
                INSERT INTO methodology_chunks (chunk_id, document_id, document_sha256, page, segment,
                                                section, section_title, equations, content, index_version)
                VALUES (:chunk_id, :document_id, :document_sha256, :page, :segment,
                        :section, :section_title, :equations, :content, :index_version)
            """), rows)
            if is_sqlite():
                conn.execute(text(
                    "INSERT INTO methodology_chunks_fts (chunk_id, section_title, content) "
                    "VALUES (:chunk_id, :section_title, :content)"), rows)
        conn.commit()
    return {"document_id": doc_id, "status": "indexed", "chunks": len(chunks), "sha256": sha}


def ingest_all() -> list[dict]:
    from src.methodology_registry import list_documents
    return [ingest_document(d) for d in list_documents()]


def index_status() -> list[dict]:
    from src.methodology_registry import list_documents
    with get_db_connection() as conn:
        rows = conn.execute(text("""
            SELECT document_id, document_sha256, COUNT(*) AS chunks, MAX(page) AS pages,
                   MIN(index_version) AS index_version
            FROM methodology_chunks GROUP BY document_id, document_sha256 ORDER BY document_id
        """)).mappings().fetchall()
    indexed = {r["document_id"]: dict(r) for r in rows}
    result = []
    for document in list_documents():
        row = indexed.get(document["document_id"])
        state = "not_indexed" if document.get("file_path") else "external_reference"
        if row:
            state = "indexed" if (row["document_sha256"] == document.get("sha256")
                                  and row["index_version"] == INDEX_VERSION) else "stale"
        result.append({"document_id": document["document_id"], "title": document["title"],
                       "document_sha256": row["document_sha256"] if row else None,
                       "chunks": row["chunks"] if row else 0, "pages": row["pages"] if row else 0,
                       "index_version": row["index_version"] if row else None, "status": state})
    return result


def _fts_query(query: str) -> str:
    terms = re.findall(r"[A-Za-z0-9]{2,}", query)
    return " OR ".join(f'"{t}"' for t in terms[:30])


def search(query: str, document_ids: list[str], limit: int = 8, *, org_id: str | None = None) -> list[dict]:
    """Full-text search restricted to `document_ids` (callers pass the
    project's resolved bundle documents — never the whole library)."""
    if not document_ids or not query.strip():
        return []
    params = {f"d{i}": d for i, d in enumerate(document_ids)}
    in_clause = ", ".join(f":d{i}" for i in range(len(document_ids)))
    with get_db_connection() as conn:
        if is_sqlite():
            fts = _fts_query(query)
            if not fts:
                return []
            rows = conn.execute(text(f"""
                SELECT c.* FROM methodology_chunks_fts f
                JOIN methodology_chunks c ON c.chunk_id = f.chunk_id
                WHERE methodology_chunks_fts MATCH :q AND c.document_id IN ({in_clause})
                ORDER BY bm25(methodology_chunks_fts), c.document_id, c.page, c.segment LIMIT :limit
            """), {**params, "q": fts, "limit": limit}).mappings().fetchall()
        else:
            rows = conn.execute(text(f"""
                SELECT *, ts_rank(search, websearch_to_tsquery('english', :q)) AS rank
                FROM methodology_chunks
                WHERE search @@ websearch_to_tsquery('english', :q) AND document_id IN ({in_clause})
                ORDER BY rank DESC, document_id, page, segment LIMIT :limit
            """), {**params, "q": query, "limit": limit}).mappings().fetchall()
    chunks = [{k: v for k, v in dict(r).items() if k not in ("search", "rank")} for r in rows]
    return attach_corrections(chunks, org_id=org_id, document_ids=document_ids)


_EQ_REF = re.compile(r"Eqs?\.\s*(\d+)(?:\s*[-–/]\s*(\d+))?")


def chunks_for_reference(document_id: str, source_section: str, limit: int = 6, *,
                         org_id: str | None = None, document_ids: list[str] | None = None) -> list[dict]:
    """Requirement-anchored retrieval: parses a registry `source_section`
    like "§5.1 (Eqs. 1-3)" or "§8.2.4 Eq. 8/9" and returns the chunks for
    those sections/equations directly, without relying on search."""
    from src.methodology_corrections import _sections
    if document_ids is not None and document_id not in document_ids:
        return []
    sections = _sections(source_section)
    equations = set()
    for a, b in _EQ_REF.findall(source_section or ""):
        lo, hi = int(a), int(b) if b else int(a)
        if hi < lo or hi - lo > 20:
            hi = lo
        equations.update(str(n) for n in range(lo, hi + 1))
    if not sections and not equations:
        return []
    with get_db_connection() as conn:
        rows = [dict(r) for r in conn.execute(text(
            "SELECT * FROM methodology_chunks WHERE document_id = :d ORDER BY page, segment"
        ), {"d": document_id}).mappings().fetchall()]
    picked = []
    for r in rows:
        in_section = any(r["section"].lower() == s or r["section"].lower().startswith(s + ".") for s in sections)
        has_eq = bool(equations & set(filter(None, r["equations"].split(","))))
        if in_section or has_eq:
            picked.append({k: v for k, v in r.items() if k != "search"})
    return attach_corrections(picked[:limit], org_id=org_id, document_ids=document_ids,
                              reference=source_section)
