"""Curated correction links, not readiness determinations.

Manifest transcribed from the two local correction PDFs on 2026-09-30.
Pages are one-based PDF pages. VM0042 numbers its 12 items separately from
their clarification/correction labels. VT0014 has three items. Summaries
are editorial metadata, never verbatim quotations or engine inputs.

Reference links are global, like methodology_documents. Confirmations are
organization-scoped: a tenant admin cannot approve a mapping for everyone.
Confirmation applies to the mapping and document hashes, not compliance.
"""
import hashlib
import json
import re

from sqlalchemy import text

from src.persistence.database import get_db_connection


def _item(doc, target, number, label, first, last, section, equations, summary):
    return {
        "id": f"{doc}:item{number}", "correction_document_id": doc,
        "item_number": number, "item_label": label,
        "correction_page": first, "correction_end_page": last,
        "target_document_id": target, "target_section": section,
        "target_equations": equations, "change_summary": summary,
    }


_VM = "vm0042-cc-2026-06-11"
_VT = "vt0014-cc-2025-10-16"
CORRECTION_LINKS = (
    _item(_VM, "vm0042-v2.2", 1, "Clarification 1", 2, 3, "6", "",
          "Appendix 3 justifies the baseline at methodology level; individual projects "
          "need not repeat that analysis. The stated target is Section 6."),
    _item(_VM, "vm0042-v2.2", 2, "Clarification 2", 3, 4, "6", "",
          "Table 4 clarifies qualitative specifications for crop planting and harvesting, "
          "including crop types, rotation, cover crops and intercropping."),
    _item(_VM, "vm0042-v2.2", 3, "Clarification 3", 4, 8, "6", "",
          "Clarifies baseline descriptions for grouped projects, eligibility areas and new "
          "instances. Includes Box 2 and the historical schedule requirement: at least "
          "three years and one complete crop rotation where applicable."),
    _item(_VM, "vm0042-v2.2", 4, "Clarification 4", 8, 9, "7", "",
          "VT0008 Step 2 barrier analysis focuses on the project activity. Specifies "
          "acceptable publicly available, transparent and verifiable evidence."),
    _item(_VM, "vm0042-v2.2", 5, "Clarification 5", 9, 10, "7", "",
          "Clarifies the geographic scope of common-practice analysis and VT0008 Step 4c. "
          "Nall and Ndiff use land area in the same region; the count threshold does not apply."),
    _item(_VM, "vm0042-v2.2", 6, "Clarification 6", 10, 11, "8.1", "",
          "Quantification units and eligibility areas in grouped projects can be determined "
          "independently; a unit can span eligibility areas or subdivide one."),
    _item(_VM, "vm0042-v2.2", 7, "Clarification 7", 11, 12, "8.2.1.4", "",
          "Changing laboratory or adopting a new eligible SOC analytical method requires "
          "justification and comparability over time, including conversion factors where needed."),
    _item(_VM, "vm0042-v2.2", 8, "Correction 1", 12, 12, "8.2.7", "12",
          "Removes the day denominator from VSl,i,t,P in Equation 12: Equation 13 already "
          "multiplies values across the year. The redlined PDF must be viewed for the unit; "
          "plain text extraction retains the deleted text."),
    _item(_VM, "vm0042-v2.2", 9, "Clarification 8", 12, 13, "8.3", "",
          "Under Quantification Approach 2, both baseline control and project SOC must be "
          "remeasured at least every five years, or before more frequent verifications."),
    _item(_VM, "vm0042-v2.2", 10, "Correction 2", 13, 13, "8.4.3", "36",
          "Corrects LKdisp,t in Equation 36 to leakage emissions from displaced production, "
          "rather than livestock displacement. It does not change the equation."),
    _item(_VM, "vm0042-v2.2", 11, "Correction 3", 13, 14, "8.5", "39,42",
          "Adds displaced-production leakage LKdisp,t to the sum of leakage sources "
          "allocated to reductions (Equation 39) and removals (Equation 42)."),
    _item(_VM, "vm0042-v2.2", 12, "Clarification 9", 15, 17, "8.6.1.3", "",
          "Clarifies remeasurement, model true-up, model validation report updates and "
          "onboarding cohorts, including back-modeling scenarios and Figure 4a. "
          "Previously issued VCUs remain unchanged."),
    _item(_VT, "vt0014-v1.0", 1, "Correction 1", 2, 2, "5.1", "5",
          "Corrects the variance units in original Equation 5 to (Mg C/ha)^2. "
          "The correction document numbers its replacement equation 1."),
    _item(_VT, "vt0014-v1.0", 2, "Correction 2", 2, 3, "5.1", "7",
          "Original Equation 7 requires the squared CO2-to-carbon molecular-weight ratio "
          "(44/12)^2 when converting variance. The correction numbers its replacement "
          "equation 2; redlined formula extraction is not reliable."),
    _item(_VT, "vt0014-v1.0", 3, "Correction 3", 3, 3, "Appendix 4", "",
          "Updates Appendix 4 computer code and unit descriptions consistently with "
          "Corrections 1 and 2, and replaces Figure 3 (probability of exceedance). "
          "The replacement figure requires visual inspection of the PDF."),
)

CORRECTION_USAGE_INSTRUCTIONS = (
    "Methodology sources may have attached corrections. Never use an affected original "
    "passage alone as authority. Prefer the applicable correction, retaining its page citation. "
    "A draft mapping is unconfirmed: disclose that limitation and do not assert that a reviewer "
    "has confirmed it. If correction text is unavailable, outside the selected bundle, stale, "
    "or requires visual interpretation, report the limitation instead of reconstructing it. "
    "Extracted correction text can retain struck-out wording and omit figures; it is not "
    "safe for verbatim quotation of amended text or equations. change_summary is curated "
    "metadata, not an exact source quote. Corrections never authorize the AI to compute values."
)


def initialize_tables(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS methodology_correction_links (
            id TEXT PRIMARY KEY,
            correction_document_id TEXT NOT NULL,
            correction_page INTEGER NOT NULL,
            correction_end_page INTEGER NOT NULL,
            item_number INTEGER NOT NULL,
            item_label TEXT NOT NULL,
            target_document_id TEXT NOT NULL,
            target_section TEXT NOT NULL DEFAULT '',
            target_equations TEXT NOT NULL DEFAULT '',
            change_summary TEXT NOT NULL,
            curated_by TEXT,
            status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'confirmed'))
        )
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_correction_target
        ON methodology_correction_links(target_document_id)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS methodology_correction_confirmations (
            org_id TEXT NOT NULL,
            correction_link_id TEXT NOT NULL,
            curated_by TEXT NOT NULL,
            confirmed_at TEXT NOT NULL,
            link_sha256 TEXT NOT NULL,
            PRIMARY KEY (org_id, correction_link_id)
        )
    """))
    for row in CORRECTION_LINKS:
        conn.execute(text("""
            INSERT INTO methodology_correction_links (
                id, correction_document_id, correction_page, correction_end_page,
                item_number, item_label, target_document_id, target_section,
                target_equations, change_summary, status)
            VALUES (:id, :correction_document_id, :correction_page, :correction_end_page,
                :item_number, :item_label, :target_document_id, :target_section,
                :target_equations, :change_summary, 'draft')
            ON CONFLICT (id) DO UPDATE SET
                correction_document_id = excluded.correction_document_id,
                correction_page = excluded.correction_page,
                correction_end_page = excluded.correction_end_page,
                item_number = excluded.item_number, item_label = excluded.item_label,
                target_document_id = excluded.target_document_id,
                target_section = excluded.target_section,
                target_equations = excluded.target_equations,
                change_summary = excluded.change_summary
        """), row)


def _list(conn, document_id=None, org_id=None):
    rows = conn.execute(text("""
        SELECT l.*, c.sha256 AS correction_sha256, t.sha256 AS target_sha256,
               f.curated_by AS confirmed_by, f.confirmed_at, f.link_sha256 AS confirmed_hash
        FROM methodology_correction_links l
        LEFT JOIN methodology_documents c ON c.document_id = l.correction_document_id
        LEFT JOIN methodology_documents t ON t.document_id = l.target_document_id
        LEFT JOIN methodology_correction_confirmations f
            ON f.correction_link_id = l.id AND f.org_id = :org
        WHERE (:doc IS NULL OR l.target_document_id = :doc OR l.correction_document_id = :doc)
        ORDER BY l.correction_document_id, l.item_number
    """), {"org": org_id, "doc": document_id}).mappings().all()
    result = []
    for raw in rows:
        row = dict(raw)
        material = {k: row[k] for k in (*CORRECTION_LINKS[0].keys(), "correction_sha256", "target_sha256")}
        row["link_sha256"] = hashlib.sha256(json.dumps(
            material, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()).hexdigest()
        previous_hash = row.pop("confirmed_hash")
        confirmed = bool(previous_hash and previous_hash == row["link_sha256"])
        row["confirmation_stale"] = bool(previous_hash and not confirmed)
        row["status"] = "confirmed" if confirmed else "draft"
        row["label"] = "confirmed" if confirmed else "unconfirmed"
        row["curated_by"] = row.pop("confirmed_by") if confirmed else None
        row.pop("confirmed_by", None)
        if not confirmed:
            row["confirmed_at"] = None
        result.append(row)
    return result


def list_corrections(document_id=None, *, org_id=None):
    with get_db_connection() as conn:
        return _list(conn, document_id, org_id)


def confirm_correction(link_id, org_id, user_id):
    """Requires a current admin in this org, even for non-HTTP callers."""
    from datetime import datetime, timezone
    with get_db_connection() as conn:
        admin = conn.execute(text(
            "SELECT 1 FROM users WHERE org_id = :org AND user_id = :user "
            "AND role = 'admin' AND is_active = 1"
        ), {"org": org_id, "user": user_id}).scalar()
        if not admin:
            raise PermissionError("Organization admin access required")
        row = next((r for r in _list(conn, org_id=org_id) if r["id"] == link_id), None)
        if row is None:
            raise LookupError("Correction link not found")
        if not row["target_section"] and not row["target_equations"]:
            raise ValueError("The correction target must be curated before confirmation")
        if not row["correction_sha256"] or not row["target_sha256"]:
            raise ValueError("Both registered source document hashes are required")
        if row["status"] != "confirmed":
            conn.execute(text("""
                INSERT INTO methodology_correction_confirmations
                    (org_id, correction_link_id, curated_by, confirmed_at, link_sha256)
                VALUES (:org, :link, :user, :time, :sha)
                ON CONFLICT (org_id, correction_link_id) DO UPDATE SET
                    curated_by = excluded.curated_by, confirmed_at = excluded.confirmed_at,
                    link_sha256 = excluded.link_sha256
            """), {"org": org_id, "link": link_id, "user": user_id,
                   "time": datetime.now(timezone.utc).isoformat(), "sha": row["link_sha256"]})
            conn.commit()
        return next(r for r in _list(conn, org_id=org_id) if r["id"] == link_id)


def _sections(reference):
    """Accept stored section keys, registry references, siblings, and appendices."""
    value = (reference or "").strip()
    found = re.findall(r"(?:§\s*|\bsections?\s+)(\d+(?:\.(?:\d+|x))*(?:/\d+(?:\.\d+)*)*)",
                       value, re.I)
    sections = [s.removesuffix(".x") for group in found for s in group.lower().split("/")]
    if re.fullmatch(r"\d+(?:\.(?:\d+|x))*", value, re.I):
        sections.append(value.lower().removesuffix(".x"))
    sections.extend("appendix " + n for n in re.findall(r"\bappendix\s+(\d+)", value, re.I))
    return sections


def _matches(link, sections, equations):
    target = link["target_section"].lower()
    if not target and not link["target_equations"]:
        return True  # Unknown target: disclose for the whole document, never silently omit.
    return any(s == target or target.startswith(s + ".") or s.startswith(target + ".")
               for s in sections) or bool(equations & set(link["target_equations"].split(",")))


_ITEM_HEADING = re.compile(r"^\s*(\d+)\s+(?:CORRECTION|CLARIFICATION)\s+\d+\s*$", re.I | re.M)


def _item_chunks(link, rows):
    """Clip to item boundaries, including when two items share a page."""
    result, active = [], False
    for raw in rows:
        row = {k: v for k, v in raw.items() if k != "search"}
        if not link["correction_page"] <= row["page"] <= link["correction_end_page"]:
            continue
        content, start, stop = row["content"], 0, None
        for heading in _ITEM_HEADING.finditer(content):
            number = int(heading.group(1))
            if number == link["item_number"]:
                active, start = True, heading.start()
            elif active and number > link["item_number"]:
                stop = heading.start()
                break
        if active and content[start:stop].strip():
            result.append({**row, "content": content[start:stop].strip(),
                           "excerpt_of_chunk_id": row["chunk_id"],
                           "chunk_id": f"{link['id']}:{row['chunk_id']}",
                           "verbatim_quote_safe": False,
                           "extraction_warning": "Redlines, equations and figures require PDF inspection."})
        if stop is not None:
            break
    return result


def corrections_for(document_id, section="", equations=(), *, org_id=None, document_ids=None):
    """Return links and indexed correction excerpts. document_ids is the bundle allowlist.

    Outside-bundle or unindexed corrections retain a warning/link, but never
    inject their text or silently permit reliance on the original alone.
    """
    if document_ids is not None and document_id not in document_ids:
        return []
    from src.methodology.library import INDEX_VERSION
    eqs = set(re.findall(r"\d+", equations)) if isinstance(equations, str) else {str(e) for e in equations}
    with get_db_connection() as conn:
        links = [r for r in _list(conn, document_id, org_id)
                 if r["target_document_id"] == document_id and _matches(r, _sections(section), eqs)]
        documents = {}
        for link in links:
            correction_doc = link["correction_document_id"]
            link["chunks"] = []
            link["review_required"] = link["status"] != "confirmed"
            link["summary_is_verbatim_quote"] = False
            if document_ids is not None and correction_doc not in document_ids:
                link["retrieval_status"] = "outside_bundle"
                continue
            if correction_doc not in documents:
                documents[correction_doc] = [dict(r) for r in conn.execute(text(
                    "SELECT * FROM methodology_chunks WHERE document_id = :doc ORDER BY page, segment"
                ), {"doc": correction_doc}).mappings().all()]
            rows = documents[correction_doc]
            if not rows:
                link["retrieval_status"] = "not_indexed"
            elif any(r["document_sha256"] != link["correction_sha256"] or r.get("index_version") != INDEX_VERSION for r in rows):
                link["retrieval_status"] = "stale_index"
            else:
                link["chunks"] = _item_chunks(link, rows)
                pages = {r["page"] for r in link["chunks"]}
                expected = set(range(link["correction_page"], link["correction_end_page"] + 1))
                link["retrieval_status"] = "available" if expected <= pages else "incomplete_extraction"
    return links


def attach_corrections(chunks, *, org_id=None, document_ids=None, reference=""):
    output = []
    correction_documents = {r["correction_document_id"] for r in CORRECTION_LINKS}
    for chunk in chunks:
        section = " ".join(f"Section {s}" for s in _sections(chunk.get("section", "")))
        links = corrections_for(chunk["document_id"], f"{section} {reference}",
                                chunk.get("equations", ""), org_id=org_id, document_ids=document_ids)
        output.append({**chunk, "corrections": links,
                       "source_is_correction": chunk["document_id"] in correction_documents,
                       "verbatim_quote_safe": chunk["document_id"] not in correction_documents and not bool(links),
                       "superseded_by_correction": bool(links),
                       "correction_review_required": any(r["review_required"] for r in links),
                       "original_text_usable_alone": not bool(links),
                       "correction_instructions": CORRECTION_USAGE_INSTRUCTIONS
                       if links or chunk["document_id"] in correction_documents else None})
    return output
