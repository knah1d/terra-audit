"""
Regression tests for the issuance gate (see src/carbon/issuance.py) and
for the retirement of src.persistence.database.commit_carbon_credit_result,
which used to be the single legacy write path for both methodologies.

The bug the issuance-gate tests lock down: app.py used to call
save_credit_history BEFORE checking VM0051's QA3 project-size gate, so a
project that failed the gate still left a credit_history row behind —
while the API path checked first. Two clients, one database, two
different answers to "was this issued."

commit_carbon_credit_result itself is now retired for EVERY field_type
(ALM first, then rice_awd — see its own docstring): a client-supplied,
un-frozen area_ha could otherwise determine recorded credits with no
evidence snapshot behind it. The evidence-linked Calculations workflow
(src.carbon.calculations.commit_calculation) is the only remaining write
path and applies this same result_is_issuable() rule itself.
"""

import pytest
from sqlalchemy import text

from src.carbon.issuance import NonIssuableResultError, result_is_issuable


def _credit_history_count(db, org_id: str, field_id: str) -> int:
    with db.get_db_connection() as conn:
        return conn.execute(
            text("SELECT COUNT(*) FROM credit_history WHERE org_id = :o AND field_id = :f"),
            {"o": org_id, "f": field_id},
        ).scalar()


# --- the pure rule ------------------------------------------------------

def test_qa3_blocked_result_is_not_issuable():
    ok, reason = result_is_issuable({"qa3_pathway_valid": False, "qa3_block_reason": "too big"})
    assert ok is False
    assert "too big" in reason


def test_leakage_blocked_result_is_not_issuable():
    ok, reason = result_is_issuable({
        "production_decline_leakage_blocked": True,
        "leakage_block_reason": "yield declined",
    })
    assert ok is False
    assert "yield declined" in reason


def test_clean_result_is_issuable():
    assert result_is_issuable({"qa3_pathway_valid": True, "final_issuance": 12.5}) == (True, None)


def test_result_missing_flags_defaults_to_issuable():
    # A third methodology with no such gate, or an older stored result,
    # must not be silently rejected.
    assert result_is_issuable({"final_issuance": 1.0}) == (True, None)


# --- the retired write path -----------------------------------------

def test_commit_refuses_qa3_blocked_result_and_writes_nothing(isolated_db):
    db = isolated_db
    db.create_field("org1", "F-1", "F", "D", {"type": "Feature", "properties": {},
                                              "geometry": None}, 1.0, "rice_awd")

    with pytest.raises(NonIssuableResultError):
        db.commit_carbon_credit_result(
            "org1", "F-1", "key-1", "rice_awd",
            {"area_ha": 1.0},
            {"final_issuance": 0.0, "qa3_pathway_valid": False,
             "qa3_block_reason": "exceeds 60,000 tCO2e/yr gate"},
        )

    assert _credit_history_count(db, "org1", "F-1") == 0


def test_commit_refuses_leakage_blocked_result_and_writes_nothing(isolated_db):
    db = isolated_db
    db.create_field("org1", "F-2", "F", "D", {"type": "Feature", "properties": {},
                                              "geometry": None}, 1.0, "cropland_alm_vm0042")

    with pytest.raises(NonIssuableResultError):
        db.commit_carbon_credit_result(
            "org1", "F-2", "key-2", "cropland_alm_vm0042",
            {"area_ha": 1.0},
            {"final_issuance": 0.0, "production_decline_leakage_blocked": True,
             "leakage_block_reason": "project yield below baseline"},
            new_cumulative_delta=99.0,
        )

    assert _credit_history_count(db, "org1", "F-2") == 0
    # The cumulative SOC delta must not have moved either — that write is
    # in the same transaction and must roll back with it.
    assert db.get_alm_cumulative_delta("org1", "F-2") == 0.0


@pytest.mark.parametrize("field_type", ["rice_awd", "cropland_alm_vm0042"])
def test_commit_refuses_an_otherwise_issuable_result_for_every_field_type(isolated_db, field_type):
    """The write path is RETIRED, not merely re-validated: even a clean,
    issuable result must be refused and nothing written — area_ha in
    `inputs` here is client-supplied and un-frozen, which is exactly what
    retirement exists to stop from ever reaching credit_history again."""
    db = isolated_db
    db.create_field("org1", "F-3", "F", "D", {"type": "Feature", "properties": {},
                                              "geometry": None}, 1.0, field_type)

    with pytest.raises(NonIssuableResultError):
        db.commit_carbon_credit_result(
            "org1", "F-3", "key-3", field_type,
            {"area_ha": 999999.0},  # implausible client-supplied value
            {"final_issuance": 12.5, "qa3_pathway_valid": True},
        )

    assert _credit_history_count(db, "org1", "F-3") == 0
    assert db.get_alm_cumulative_delta("org1", "F-3") == 0.0
