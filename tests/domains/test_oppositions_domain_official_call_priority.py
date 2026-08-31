"""Phase 10.23 — OfficialCallPriorityRule tests (frozen spec §36)."""

from __future__ import annotations

from cmm.domains.oppositions.rules import (
    PROVENANCE_GROUNDED,
    SOURCE_CLASS_OFFICIAL_PUBLICATION,
    SOURCE_CLASS_PERSONAL_NOTE,
    SOURCE_CLASS_REGULATION,
    SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
    SPECIFICITY_GENERAL,
    SPECIFICITY_SPECIFIC,
    TEMPORAL_VALID,
    classify_opposition_source_authority,
)

_G = {
    "provenance": PROVENANCE_GROUNDED,
    "temporal": TEMPORAL_VALID,
}


def _call(source_id, value, *, scope=None):
    s = {
        **_G,
        "source_id": source_id,
        "source_class": SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
        "specificity": SPECIFICITY_SPECIFIC,
        "value": value,
        "supplied_attributes": ("application_deadline",),
    }
    if scope is not None:
        s["scope"] = scope
    return s


def _note(source_id, value):
    return {
        **_G,
        "source_id": source_id,
        "source_class": SOURCE_CLASS_PERSONAL_NOTE,
        "specificity": SPECIFICITY_GENERAL,
        "value": value,
        "supplied_attributes": ("application_deadline",),
    }


def test_specific_official_call_beats_incompatible_personal_note():
    result = classify_opposition_source_authority(
        attribute="application_deadline",
        sources=(
            _note("note1", "2026-09-01"),
            _call("call1", "2026-08-31", scope="body:admin"),
        ),
        scope="body:admin",
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "call1"
    assert result["authoritative_value"] == "2026-08-31"


def test_specific_official_publication_controls_exam_date_in_scope():
    pub = {
        **_G,
        "source_id": "pub1",
        "source_class": SOURCE_CLASS_OFFICIAL_PUBLICATION,
        "specificity": SPECIFICITY_SPECIFIC,
        "value": "2027-03-15",
        "supplied_attributes": ("exam_date",),
        "scope": "body:admin",
    }
    note = {
        **_G,
        "source_id": "note1",
        "source_class": SOURCE_CLASS_PERSONAL_NOTE,
        "value": "2027-03-20",
        "supplied_attributes": ("exam_date",),
        "scope": "body:admin",
    }
    result = classify_opposition_source_authority(
        attribute="exam_date", sources=(note, pub), scope="body:admin"
    )
    assert result["authoritative_source_id"] == "pub1"
    assert result["authoritative_value"] == "2027-03-15"


def test_regulation_controls_general_requirement_only_in_scope():
    reg = {
        **_G,
        "source_id": "reg1",
        "source_class": SOURCE_CLASS_REGULATION,
        "specificity": SPECIFICITY_SPECIFIC,
        "value": "18",
        "supplied_attributes": ("eligibility_requirement",),
        "scope": "body:admin",
    }
    unrelated = {
        **_G,
        "source_id": "callX",
        "source_class": SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
        "value": "16",
        "supplied_attributes": ("eligibility_requirement",),
        "scope": "body:other",
    }
    result = classify_opposition_source_authority(
        attribute="eligibility_requirement",
        sources=(unrelated, reg),
        scope="body:admin",
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "reg1"


def test_recency_alone_does_not_override_authority():
    # newer personal note cannot override the grounded specific official call
    result = classify_opposition_source_authority(
        attribute="application_deadline",
        sources=(
            _call("call1", "2026-08-31", scope="body:admin"),
            _note("note_new", "2026-09-05"),
        ),
        scope="body:admin",
    )
    assert result["authoritative_source_id"] == "call1"


def test_caller_official_true_does_not_create_authority():
    # A caller label ``official=True`` never upgrades an ungrounded source to
    # authority: provenance is not truth.
    fake = {
        "source_id": "fake1",
        "official": True,  # caller label only
        "source_class": SOURCE_CLASS_PERSONAL_NOTE,
        "provenance": "caller_claimed",
        "temporal": TEMPORAL_VALID,
        "specificity": SPECIFICITY_GENERAL,
        "value": "2026-08-31",
        "supplied_attributes": ("application_deadline",),
        "scope": "body:admin",
    }
    result = classify_opposition_source_authority(
        attribute="application_deadline",
        sources=(fake,),
        scope="body:admin",
    )
    # caller official flag never creates authority
    assert result["authority_resolved"] is False
    assert result["authoritative_source_id"] is None


def test_provenance_alone_does_not_create_truth():
    unclassed = {
        "source_id": "s1",
        "provenance": PROVENANCE_GROUNDED,
        "value": "x",
        "supplied_attributes": ("application_deadline",),
        "scope": "body:admin",
    }
    result = classify_opposition_source_authority(
        attribute="application_deadline", sources=(unclassed,), scope="body:admin"
    )
    assert result["authority_resolved"] is False


def test_missing_reference_cannot_confirm_material_fact():
    no_ref = {
        **_G,
        "source_id": "s1",
        "source_class": SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
        "value": "2026-08-31",
        "supplied_attributes": ("exam_date",),
        "scope": "body:admin",
    }
    result = classify_opposition_source_authority(
        attribute="exam_date",
        sources=(no_ref,),
        scope="body:admin",
        require_reference=True,
    )
    assert result["authority_resolved"] is False
    assert result["reason"] == "missing_usable_reference"


def test_equal_authority_agreeing_evidence_corroborates():
    call = _call("call1", "2026-08-31", scope="body:admin")
    call2 = _call("call2", "2026-08-31", scope="body:admin")
    result = classify_opposition_source_authority(
        attribute="application_deadline",
        sources=(call, call2),
        scope="body:admin",
    )
    assert result["authority_resolved"] is True
    assert result["conflict"] is False
    assert result["reason"] == "corroborated"


def test_equal_authority_incompatible_remains_unresolved():
    call = _call("call1", "2026-08-31", scope="body:admin")
    call2 = _call("call2", "2026-09-10", scope="body:admin")
    result = classify_opposition_source_authority(
        attribute="application_deadline",
        sources=(call, call2),
        scope="body:admin",
    )
    assert result["authority_resolved"] is False
    assert result["conflict"] is True
    assert result["reason"] == "equal_authority_conflict"


def test_grounded_supersession_works():
    replacement = {
        **_G,
        "source_id": "call2027",
        "source_class": SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
        "specificity": SPECIFICITY_SPECIFIC,
        "value": "2027-05-01",
        "supplied_attributes": ("exam_date",),
        "scope": "body:admin",
        "supersedes": ("call2026",),
    }
    old = {
        **_G,
        "source_id": "call2026",
        "source_class": SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
        "specificity": SPECIFICITY_SPECIFIC,
        "value": "2026-05-01",
        "supplied_attributes": ("exam_date",),
        "scope": "body:admin",
    }
    result = classify_opposition_source_authority(
        attribute="exam_date", sources=(old, replacement), scope="body:admin"
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "call2027"
    assert "call2026" in result["superseded_sources"]


def test_ungrounded_self_declared_supersession_fails():
    ungrounded_new = {
        "source_id": "new1",
        "source_class": SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
        "specificity": SPECIFICITY_SPECIFIC,
        "value": "2027-05-01",
        "supplied_attributes": ("exam_date",),
        "scope": "body:admin",
        "supersedes": ("old1",),
    }
    old = {
        **_G,
        "source_id": "old1",
        "source_class": SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
        "specificity": SPECIFICITY_SPECIFIC,
        "value": "2026-05-01",
        "supplied_attributes": ("exam_date",),
        "scope": "body:admin",
    }
    result = classify_opposition_source_authority(
        attribute="exam_date", sources=(old, ungrounded_new), scope="body:admin"
    )
    # ungrounded "new" is not grounded/current -> not a candidate; old cannot be
    # superseded, so authority either resolves to old or stays unknown-because-no
    # grounded replacement.  It must never demote old on a mere declaration.
    assert "old1" not in result["superseded_sources"]


def test_temporally_unknown_high_authority_keeps_uncertainty():
    unknown = {
        "source_id": "mystery",
        "source_class": SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
        "provenance": PROVENANCE_GROUNDED,
        "temporal": "unknown",
        "specificity": SPECIFICITY_SPECIFIC,
        "value": "2027-01-01",
        "supplied_attributes": ("exam_date",),
        "scope": "body:admin",
    }
    lower = {
        **_G,
        "source_id": "note1",
        "source_class": SOURCE_CLASS_PERSONAL_NOTE,
        "value": "2026-06-01",
        "supplied_attributes": ("exam_date",),
        "scope": "body:admin",
    }
    result = classify_opposition_source_authority(
        attribute="exam_date", sources=(lower, unknown), scope="body:admin"
    )
    assert result["authority_resolved"] is False
    assert result["conflict"] is True


def test_expired_history_stays_historical():
    expired = {
        "source_id": "old1",
        "source_class": SOURCE_CLASS_SPECIFIC_OFFICIAL_CALL,
        "provenance": PROVENANCE_GROUNDED,
        "temporal": "expired",
        "specificity": SPECIFICITY_SPECIFIC,
        "value": "2020-05-01",
        "supplied_attributes": ("exam_date",),
        "scope": "body:admin",
    }
    result = classify_opposition_source_authority(
        attribute="exam_date", sources=(expired,), scope="body:admin"
    )
    # expired is not current -> not a current authoritative value
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False


def test_malformed_scope_never_global():
    call = _call("call1", "2026-08-31")
    result = classify_opposition_source_authority(
        attribute="application_deadline",
        sources=(call,),
        scope=7,  # malformed requested scope
    )
    assert result["authority_resolved"] is False
    assert result["reason"] == "malformed_requested_scope"


def test_malformed_source_scope_fails_closed():
    bad = {
        **_G,
        "source_id": "s1",
        "source_class": SOURCE_CLASS_PERSONAL_NOTE,
        "value": "2026-08-31",
        "supplied_attributes": ("application_deadline",),
        "scope": 7,
    }
    result = classify_opposition_source_authority(
        attribute="application_deadline", sources=(bad,)
    )
    assert result["authority_resolved"] is False


def test_input_permutation_same_semantic_result():
    a = (_note("n1", "2026-09-01"), _call("c1", "2026-08-31", scope="body:admin"))
    b = (_call("c1", "2026-08-31", scope="body:admin"), _note("n1", "2026-09-01"))
    r1 = classify_opposition_source_authority(
        attribute="application_deadline", sources=a, scope="body:admin"
    )
    r2 = classify_opposition_source_authority(
        attribute="application_deadline", sources=b, scope="body:admin"
    )
    assert r1["authoritative_source_id"] == r2["authoritative_source_id"]
    assert r1["authoritative_value"] == r2["authoritative_value"]
