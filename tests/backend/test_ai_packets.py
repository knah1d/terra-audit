"""Read-only explanation packets: isolation, provenance, determinism and budgets."""
import json

import pytest
from sqlalchemy import text

from src.carbon import calculations
from src.persistence import database
from src.methodology import library
from src.methodology import registry
from src.evidence import monitoring
from src.evidence import production as production_records
from src.projects import repository as projects
from src.methodology import readiness
from src.evidence import soil as soil_evidence
from src.ai import packets
from src.projects.reviews import diff_calculations


@pytest.fixture()
def scope(isolated_db, seeded_users):
    actor = seeded_users["admin"]
    pid = projects.create_project("testorg", "Packet project", "", "", None, None, "active", actor)
    database.create_field("testorg", "PACKET-FIELD", "Wheat and maize field", "District", {}, 10.0, "cropland_alm_vm0042")
    membership = projects.assign_field_to_project("testorg", pid, "PACKET-FIELD", "2020-01-01", actor)
    projects.add_project_member("testorg", pid, seeded_users["viewer"], "viewer", actor)
    return {"org_id": "testorg", "project_id": pid, "user_id": actor, "field_id": "PACKET-FIELD",
            "membership_id": membership, "viewer": seeded_users["viewer"]}


def args(scope):
    return {k: scope[k] for k in ("org_id", "project_id", "user_id", "field_id")}


def store_calc(scope, cid="calc-a", previous=None, result=None, checks=None):
    bundle_id = registry.resolve_bundle_for_project(scope["org_id"], scope["project_id"], "vm0042_alm")["bundle_id"]
    values = {**args(scope), "cid": cid, "previous": previous, "version": 2 if previous else 1,
              "inputs": json.dumps({"verification_years": 2}),
              "snapshot": json.dumps({"field": {"field_id": scope["field_id"]},
                  "project_id": scope["project_id"], "seasons": [],
                  "methodology_bundle": registry.get_bundle(bundle_id)}, default=str),
              "result": json.dumps(result or {"final_issuance": None, "soc_uncertainty_annualization_unresolved": True}),
              "checks": json.dumps(checks or [{"requirement_id": "vm0042.soc_uncertainty_annualization",
                                              "status": "unsupported", "explanation": "Verification period is not annual."}])}
    with database.get_db_connection() as conn:
        conn.execute(text("""INSERT INTO calculations (
            org_id, calculation_id, chain_id, version, supersedes_calculation_id, project_id,
            field_id, field_type, accounting_pathway, monitoring_period_start, monitoring_period_end,
            season_ids, snapshot_json, inputs_json, result_json, readiness_json, methodology_version,
            engine_version, created_by, bundle_id)
            VALUES (:org_id, :cid, 'chain-a', :version, :previous, :project_id, :field_id,
                'cropland_alm_vm0042', 'vm0042_alm', '2026-01-01', '2026-12-31', '[]',
                :snapshot, :inputs, :result, :checks, 'VM0042 v2.2',
                'fixture-v1', :user_id, 'vm0042-2026-06')"""), values)
        conn.commit()
    return cid


def test_sentence_ids_preserve_rows_and_cap_long_text():
    text_value = "First sentence. Next sentence.\n\n- item 1\nA | 12.3 | 4\n" + "long " * 120
    sentences = packets.split_sentences("source", text_value)
    assert [s["id"] for s in sentences] == [f"source:s{n}" for n in range(1, len(sentences) + 1)]
    assert all(len(s["text"]) <= 400 for s in sentences)
    assert any(s["text"] == "- item 1" for s in sentences)
    assert any(s["text"] == "A | 12.3 | 4" for s in sentences)
    assert len(packets.split_sentences("source", "row\n" * 100)) == packets.MAX_SOURCE_SENTENCES


def test_same_state_same_hash_and_no_readiness_or_calculation_writes(scope):
    cid = store_calc(scope)
    before = calculations.get_calculation(scope["org_id"], cid)
    one = packets.explain_block(**args(scope), calculation_id=cid)
    two = packets.explain_block(**args(scope), calculation_id=cid)
    assert one == two
    assert len(one["context_sha256"]) == 64
    assert any(f["kind"] == "engine_gate" and f["data"]["result_is_issuable"] is False for f in one["facts"])
    assert any("missing (null)" in sentence["text"] for s in one["sources"]
               if s["id"] == f"calculation:{cid}:final_issuance" for sentence in s["sentences"])
    assert calculations.get_calculation(scope["org_id"], cid) == before
    with database.get_db_connection() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM readiness_determinations")).scalar() == 0


def test_authorized_viewer_can_build_but_other_org_and_inactive_field_cannot(scope, seeded_users):
    cid = store_calc(scope)
    viewer_args = {**args(scope), "user_id": scope["viewer"]}
    assert packets.explain_block(**viewer_args, calculation_id=cid)["calculation_id"] == cid
    with pytest.raises(PermissionError):
        packets.explain_block(**{**args(scope), "user_id": seeded_users["other_org_admin"]}, calculation_id=cid)
    projects.end_project_field_membership(scope["org_id"], scope["membership_id"], "2026-01-01", "removed")
    with pytest.raises(PermissionError):
        packets.explain_block(**args(scope), calculation_id=cid)


def test_calculation_must_belong_to_selected_project(scope):
    cid = store_calc(scope)
    other = projects.create_project(scope["org_id"], "Other project", "", "", None, None, "active", scope["user_id"])
    # One project per field at a time: the field leaves the first project before joining the other.
    projects.end_project_field_membership(scope["org_id"], scope["membership_id"], "2020-12-31", "Moved to other project")
    projects.assign_field_to_project(scope["org_id"], other, scope["field_id"], "2021-01-01", scope["user_id"])
    with pytest.raises(ValueError, match="Calculation not found"):
        packets.explain_block(**{**args(scope), "project_id": other}, calculation_id=cid)


def test_new_season_and_unadopted_soil_sample_change_fingerprint(scope):
    initial = packets.evidence_fingerprint(**args(scope))
    monitoring.append_record("crop_seasons", scope["org_id"], scope["field_id"], None,
                             {"crops": ["wheat"], "start_date": "2023-01-01", "end_date": "2023-12-31", "is_historical": True})
    with_season = packets.evidence_fingerprint(**args(scope))
    assert initial != with_season
    plan = soil_evidence.create_plan(scope["org_id"], scope["field_id"], "Plan", "", "dry_combustion", 5, scope["user_id"])
    before_sample = packets.evidence_fingerprint(**args(scope))
    soil_evidence.create_sample(scope["org_id"], plan, scope["field_id"], None, "project", "t_start",
        "2026-01-01", 0, 30, None, None, 1.2, None, None, "Lab", "Method", "Custody", "", scope["user_id"])
    assert before_sample != packets.evidence_fingerprint(**args(scope))


def test_missing_evidence_has_static_fix_link_and_no_invented_verification_year(scope):
    packet = packets.missing_evidence(**args(scope), monitoring_period_start="2026-01-01",
        monitoring_period_end="2026-12-31", season_ids=[], requirement_id="vm0042.soc_measurements")
    checks = [f["data"] for f in packet["facts"] if f["kind"] == "readiness"]
    assert len(checks) == 1 and checks[0]["fix"]["route"] == "/fields/PACKET-FIELD/soil-evidence"
    assert packet["allowed_requirement_ids"] == ["vm0042.soc_measurements"]
    unknown_period = packets.missing_evidence(**args(scope), monitoring_period_start="2026-01-01",
        monitoring_period_end="2026-12-31", season_ids=[], requirement_id="vm0042.soc_uncertainty_annualization")
    annualization = next(f["data"] for f in unknown_period["facts"] if f["kind"] == "readiness")
    assert annualization["status"] == "needs_review" and "not been supplied" in annualization["explanation"]


def test_applicability_is_project_scoped_and_does_not_contain_other_tenant_records(scope):
    database.create_field("otherorg", "SECRET-FOREIGN-FIELD", "Private foreign farm", "", {}, 12, "rice_awd")
    packet = packets.applicable_requirements(**args(scope))
    assert packet["bundle_id"] == "vm0042-2026-06"
    assert packet["allowed_requirement_ids"]
    assert "SECRET-FOREIGN-FIELD" not in packets.canonical_json(packet)
    assert not any(s.get("document_id", "").startswith("vm0051") for s in packet["sources"])
    assert packet == packets.applicable_requirements(**args(scope))
    assert packet["estimated_tokens"] <= packets.DEFAULT_PACKET_TOKENS
    assert len(packets.canonical_json(packet)) <= packets.DEFAULT_PACKET_TOKENS * 4
    requirements = registry.list_requirements(packet["bundle_id"])
    facts = {f["data"]["requirement_id"]: f["data"]
             for f in packet["facts"] if f["kind"] == "readiness"}
    assert set(facts) == {r["requirement_id"] for r in requirements}
    sources = {s["id"]: s for s in packet["sources"]}
    for requirement in requirements:
        rid = requirement["requirement_id"]
        # Budget compaction must not drop evidence text, blocking flags,
        # implementation limitations or reviewer authority from any fact.
        assert all(facts[rid][key] == value for key, value in requirement.items())
        citation = sources[f"readiness:{rid}"]
        text_value = " ".join(s["text"] for s in citation["sentences"])
        assert " ".join(requirement["required_evidence"].split()) in " ".join(text_value.split())
        assert not citation.get("truncated", False)


def test_diff_without_previous_skips_model_and_diff_reuses_review_logic(scope):
    first = store_calc(scope, result={"final_issuance": 12.3, "leakage": {"integrated": True, "computable": True}})
    no_previous = packets.diff_since_previous(**args(scope), calculation_id=first)
    assert no_previous["call_model"] is False and no_previous["deterministic_message"] == "No previous version"
    second = store_calc(scope, cid="calc-b", previous=first,
                        result={"final_issuance": 10.0, "leakage": {"integrated": True, "computable": True}},
                        checks=[{"requirement_id": "vm0042.soc_uncertainty_annualization", "status": "not_applicable"}])
    packet = packets.diff_since_previous(**args(scope), calculation_id=second)
    comparison = next(f["data"] for f in packet["facts"] if f["kind"] == "comparison")
    assert comparison == diff_calculations(calculations.get_calculation(scope["org_id"], second),
                                          calculations.get_calculation(scope["org_id"], first))
    assert comparison["result_changed"]["final_issuance"] == {"current": 10.0, "previous": 12.3}


def test_leakage_explains_stored_result_without_recomputing(scope, monkeypatch):
    cid = store_calc(scope, result={"final_issuance": None, "leakage": {
        "computable": False, "AL_t_ha": 2.5, "leakage_block_reason": "Regional carbon stock parameters missing."}})
    def forbidden(*a, **kw):
        raise AssertionError("Stored leakage must not be recomputed")
    monkeypatch.setattr("src.carbon.leakage_vmd0054.calculate_frozen_leakage", forbidden)
    packet = packets.explain_leakage(**args(scope), calculation_id=cid)
    result = next(f["data"] for f in packet["facts"] if f["kind"] == "leakage_result")
    assert result["AL_t_ha"] == 2.5 and result["computable"] is False


def test_small_budget_rejects_instead_of_truncating_essential_facts(scope):
    cid = store_calc(scope)
    with pytest.raises(packets.PacketTooLargeError):
        packets.explain_block(**args(scope), calculation_id=cid, max_tokens=20)


def test_corrected_sections_attach_draft_links_and_truncate_only_references(scope):
    for doc in registry.list_documents():
        if doc["document_id"] in {"vm0042-v2.2", "vm0042-cc-2026-06-11"}:
            library.ingest_document(doc)
    cid = store_calc(scope, checks=[{"requirement_id": "vm0042.historical_lookback", "status": "missing", "explanation": "Baseline history is missing."}])
    packet = packets.explain_block(**args(scope), calculation_id=cid)
    corrections = [s for s in packet["sources"] if s["kind"] == "correction"]
    assert corrections and all(s["label"] == "unconfirmed" for s in corrections)
    essentials = [s for s in packet["sources"] if s["kind"] not in {"methodology", "correction"}]
    smaller = packets.explain_block(**args(scope), calculation_id=cid, max_tokens=4000)
    assert smaller["truncated"] and smaller["omitted_source_ids"]
    assert smaller["facts"] == packet["facts"]
    assert [s for s in smaller["sources"] if s["kind"] not in {"methodology", "correction"}] == essentials
    assert len(packets.canonical_json(smaller)) / 4 <= 4000


def test_changed_evidence_during_build_is_rejected(scope, monkeypatch):
    original = readiness.guided_enrollment
    def mutate(*a, **kw):
        result = original(*a, **kw)
        monitoring.append_record("crop_seasons", scope["org_id"], scope["field_id"], None,
                                 {"crops": ["maize"], "start_date": "2026-01-01", "end_date": "2026-06-01"})
        return result
    monkeypatch.setattr(readiness, "guided_enrollment", mutate)
    with pytest.raises(ValueError, match="Evidence changed"):
        packets.applicable_requirements(**args(scope))


def test_requirement_removed_between_versions_stays_in_allowed_ids(scope):
    previous = store_calc(scope)
    current = store_calc(scope, cid="calc-b", previous=previous, checks=[{
        "requirement_id": "vm0042.historical_lookback", "status": "missing", "explanation": "History missing."}])
    packet = packets.diff_since_previous(**args(scope), calculation_id=current)
    assert set(packet["allowed_requirement_ids"]) == {
        "vm0042.historical_lookback", "vm0042.soc_uncertainty_annualization"}


def test_nested_snapshot_cannot_expose_other_field_samples(scope):
    cid = store_calc(scope)
    snapshot = calculations.get_calculation(scope["org_id"], cid)["snapshot"]
    snapshot["soil_evidence"] = {"plans": [{"samples": [{
        "sample_id": "foreign", "field_id": "FOREIGN-FIELD", "org_id": scope["org_id"]}]}]}
    with database.get_db_connection() as conn:
        conn.execute(text("UPDATE calculations SET snapshot_json=:snapshot WHERE calculation_id=:id"),
                     {"snapshot": json.dumps(snapshot, default=str), "id": cid})
        conn.commit()
    with pytest.raises(ValueError, match="soil sample.*another field"):
        packets.explain_block(**args(scope), calculation_id=cid)


def test_saved_assessment_action_is_deterministic_and_reports_missing_inputs(scope):
    saved = production_records.save_leakage_assessment(scope["org_id"], scope["field_id"], {
        "project_id": scope["project_id"], "bundle_id": "vm0042-2026-06",
        "monitoring_period_start": "2026-01-01", "monitoring_period_end": "2026-12-31",
        "module_version": "1.1"}, scope["user_id"])
    one = packets.explain_leakage(**args(scope), assessment_id=saved["assessment_id"])
    two = packets.explain_leakage(**args(scope), assessment_id=saved["assessment_id"])
    assert one == two
    result = next(f["data"] for f in one["facts"] if f["kind"] == "leakage_result")
    assert result["computable"] is False and result["leakage_emissions_tco2e"] is None
    assert result["leakage_block_reason"]
