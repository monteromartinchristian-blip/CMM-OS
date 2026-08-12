"""Phase 10.22 — B4: ECTS Consistency (credit buckets, no double-counting).

The audit found the previous implementation compared ECTS×hours against a
declared workload as the core consistency check.  That comparison is removed
as the core.  ECTS reasoning must instead reason over distinct credit buckets
(completed / recognized / enrolled / planned / pending-recognition / required),
never double-count a credit, never silently sum contradictory buckets, and
block a completion conclusion when a critical requirement is uncertain.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import check_ects_consistency

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _record(subject_id, ects, state, *, source="record-1", **extra):
    return {
        "subject_id": subject_id,
        "ects": ects,
        "state": state,
        "grounded": True,
        "source_reference": source,
        "temporal": "valid",
        **extra,
    }


def _canonical_result(*, records=(), degree_requirement=None, **legacy):
    rule = {
        r.definition.id: r
        for r in build_university_rules()
    }["university.ects_consistency"]
    context = ReasoningRuleContext(
        reasoning_id="ects-production",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata={
            "ects": {
                **legacy,
                "records": records,
                "degree_requirement": degree_requirement,
            }
        },
    )
    return rule.evaluate(context)


def test_recognized_credits_satisfy_requirement():
    """Completed plus officially recognized credits count toward the degree."""
    result = check_ects_consistency(
        completed=150,
        recognized=30,
        required=180,
    )
    assert result["satisfied"] is True
    assert result["completion_determinable"] is True
    assert result["completion_blocked"] is False


def test_planned_credits_do_not_count_yet():
    """Enrolled/planned credits are not yet earned and do not satisfy a
    requirement that is being assessed."""
    result = check_ects_consistency(
        completed=100,
        enrolled=30,
        planned=20,
        required=180,
    )
    assert result["satisfied"] is False
    assert result["recognized_total"] == 100


def test_pending_recognition_is_not_fully_recognized():
    """Credits pending recognition stay in a separate bucket and are not
    silently added to the recognized total."""
    result = check_ects_consistency(
        completed=100,
        pending_recognition=50,
        required=180,
    )
    assert result["recognized_total"] == 100
    assert result["satisfied"] is False


def test_double_counting_is_flagged_not_silently_summed():
    """A credit present in more than one earned bucket is double-counted and
    flagged rather than summed twice."""
    result = check_ects_consistency(
        completed=100,
        recognized=100,
        required=180,
        double_counted=("subj-a",),
    )
    assert result["double_counting"] is True
    assert result["satisfied"] is False
    assert result["completion_determinable"] is False


def test_contradictory_buckets_not_silently_reconciled():
    """When buckets contradict each other the result is flagged; the values are
    never silently summed into a confident total."""
    result = check_ects_consistency(
        completed=120,
        recognized=40,
        required=180,
        contradictory=("subj-b",),
    )
    assert result["contradiction"] is True
    assert result["completion_determinable"] is False


def test_critical_requirement_uncertain_blocks_completion():
    """A completion conclusion is blocked while a critical requirement's status
    is uncertain."""
    result = check_ects_consistency(
        completed=180,
        required=180,
        critical_requirement_uncertain=True,
    )
    assert result["completion_blocked"] is True
    assert result["satisfied"] is False


def test_clean_noncritical_case_is_determinable():
    result = check_ects_consistency(
        completed=180,
        required=180,
    )
    assert result["completion_determinable"] is True
    assert result["completion_blocked"] is False
    assert result["satisfied"] is True
    assert result["double_counting"] is False
    assert result["contradiction"] is False


def test_canonical_rule_missing_requirement_stays_unknown():
    result = _canonical_result(
        records=tuple(_record(f"subject-{i}", 30, "completed") for i in range(6)),
        degree_requirement=None,
    )
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.metadata["required"] is None
    assert finding.metadata["satisfied"] is False
    assert finding.metadata["required_known"] is False
    assert result.gaps
    assert result.gaps[0].metadata["verification_need"]["needed"] is True


def test_canonical_rule_legacy_aggregate_cannot_confirm_completion():
    result = _canonical_result(completed=180, required=180)
    finding = result.findings[0]
    assert finding.code == "ECTS_COMPLETION_BLOCKED"
    assert finding.metadata["satisfied"] is False
    assert finding.metadata["required_known"] is False
    assert finding.metadata["credit_state_sufficiently_grounded"] is False
    assert finding.metadata["verification_need"]["needed"] is True


def test_canonical_rule_same_subject_completed_and_recognized_is_not_double_counted():
    result = _canonical_result(
        records=(
            _record("subject-a", 6, "completed", source="record-complete"),
            _record("subject-a", 6, "recognized", source="record-recognized"),
        ),
        degree_requirement={"required_ects": 6, "grounded": True, "source_reference": "degree-1"},
    )
    finding = result.findings[0]
    assert finding.code == "ECTS_COMPLETION_BLOCKED"
    assert finding.metadata["double_counting"] is True
    assert "subject-a" in finding.metadata["double_counted"]
    assert finding.metadata["recognized_total"] == 12


def test_canonical_rule_enrolled_credits_do_not_count_as_completed():
    result = _canonical_result(
        records=(_record("subject-enrolled", 6, "enrolled"),),
        degree_requirement={"required_ects": 6, "grounded": True, "source_reference": "degree-1"},
    )
    finding = result.findings[0]
    assert finding.metadata["completed"] == 0
    assert finding.metadata["enrolled"] == 6
    assert finding.metadata["satisfied"] is False


def test_canonical_rule_pending_recognition_is_only_conditional():
    result = _canonical_result(
        records=(
            _record("subject-complete", 174, "completed"),
            _record("subject-pending", 6, "pending_recognition"),
        ),
        degree_requirement={
            "required_ects": 180,
            "grounded": True,
            "source_reference": "degree-1",
            "temporal": "valid",
        },
    )
    finding = result.findings[0]
    assert finding.metadata["recognized_total"] == 174
    assert finding.metadata["pending_recognition"] == 6
    assert finding.metadata["satisfied"] is False
    assert finding.metadata["scenario_if_recognized"] == 180


def test_canonical_rule_contradictory_current_credit_states_block_completion():
    result = _canonical_result(
        records=(
            _record("subject-a", 6, "completed", source="pass"),
            _record("subject-a", 6, "failed", source="fail"),
        ),
        degree_requirement={"required_ects": 6, "grounded": True, "source_reference": "degree-1"},
    )
    finding = result.findings[0]
    assert finding.code == "ECTS_COMPLETION_BLOCKED"
    assert finding.metadata["contradiction"] is True
    assert "subject-a" in finding.metadata["contradictory"]


def test_canonical_rule_grounded_records_can_confirm_completion():
    result = _canonical_result(
        records=tuple(_record(f"subject-{i}", 30, "completed") for i in range(6)),
        degree_requirement={
            "required_ects": 180,
            "grounded": True,
            "source_reference": "degree-1",
            "temporal": "valid",
        },
    )
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.code == "ECTS_REQUIREMENT_SATISFIED"
    assert finding.metadata["recognized_total"] == 180


def test_canonical_rule_record_without_source_reference_cannot_confirm_completion():
    for source in (None, "   "):
        result = _canonical_result(
            records=tuple(
                _record(f"subject-{i}", 30, "completed", source=source)
                for i in range(6)
            ),
            degree_requirement={
                "required_ects": 180,
                "grounded": True,
                "source_reference": "degree-1",
                "temporal": "valid",
            },
        )

        finding = result.findings[0]
        assert finding.code == "ECTS_COMPLETION_BLOCKED"
        assert finding.metadata["satisfied"] is False
        assert finding.metadata["credit_state_sufficiently_grounded"] is False
        assert finding.metadata["verification_need"]["needed"] is True


def test_canonical_rule_noncurrent_or_unknown_requirement_cannot_confirm_completion():
    records = tuple(_record(f"subject-{i}", 30, "completed") for i in range(6))
    for temporal in ("expired", "future", "unknown", None):
        requirement = {
            "required_ects": 180,
            "grounded": True,
            "source_reference": "degree-1",
        }
        if temporal is not None:
            requirement["temporal"] = temporal

        result = _canonical_result(
            records=records,
            degree_requirement=requirement,
        )

        finding = result.findings[0]
        assert finding.code == "ECTS_COMPLETION_BLOCKED"
        assert finding.metadata["satisfied"] is False
        assert finding.metadata["required_known"] is False
        assert finding.metadata["verification_need"]["needed"] is True


def test_canonical_rule_timeless_grounded_requirement_can_confirm_completion():
    result = _canonical_result(
        records=tuple(_record(f"subject-{i}", 30, "completed") for i in range(6)),
        degree_requirement={
            "required_ects": 180,
            "grounded": True,
            "source_reference": "degree-1",
            "temporal": "timeless",
        },
    )

    finding = result.findings[0]
    assert finding.code == "ECTS_REQUIREMENT_SATISFIED"
    assert finding.metadata["satisfied"] is True


def test_canonical_rule_unknown_structured_state_blocks_completion_conditionally():
    for state in ("unknown", "mystery"):
        result = _canonical_result(
            records=(
                _record("completed-subject", 174, "completed"),
                _record("unresolved-subject", 6, state),
            ),
            degree_requirement={
                "required_ects": 180,
                "grounded": True,
                "source_reference": "degree-1",
                "temporal": "valid",
            },
        )

        finding = result.findings[0]
        assert finding.code == "ECTS_COMPLETION_BLOCKED"
        assert finding.metadata["satisfied"] is False
        assert finding.metadata["completion_determinable"] is False
        assert finding.metadata["unknown_records"] == ("unresolved-subject",)
        assert finding.metadata["credit_state_sufficiently_grounded"] is False


def test_canonical_rule_known_failed_state_remains_deterministically_unsatisfied():
    result = _canonical_result(
        records=(
            _record("completed-subject", 174, "completed"),
            _record("failed-subject", 6, "failed"),
        ),
        degree_requirement={
            "required_ects": 180,
            "grounded": True,
            "source_reference": "degree-1",
            "temporal": "valid",
        },
    )

    finding = result.findings[0]
    assert finding.code == "ECTS_REQUIREMENT_NOT_SATISFIED"
    assert finding.metadata["satisfied"] is False
    assert finding.metadata["completion_determinable"] is True
    assert finding.metadata["unknown_records"] == ()


def test_canonical_rule_unknown_records_are_order_invariant():
    records = (
        _record("subject-z", 6, "mystery"),
        _record("subject-a", 6, "unknown"),
    )
    unknown_results = []
    for ordered_records in (records, tuple(reversed(records))):
        result = _canonical_result(
            records=ordered_records,
            degree_requirement={
                "required_ects": 12,
                "grounded": True,
                "source_reference": "degree-1",
                "temporal": "valid",
            },
        )
        unknown_results.append(result.findings[0].metadata["unknown_records"])

    assert unknown_results == [
        ("subject-a", "subject-z"),
        ("subject-a", "subject-z"),
    ]


def test_canonical_rule_malformed_degree_requirement_fails_closed():
    records = tuple(_record(f"subject-{i}", 30, "completed") for i in range(6))
    for required_ects in ("abc", -1, 0):
        result = _canonical_result(
            records=records,
            degree_requirement={
                "required_ects": required_ects,
                "grounded": True,
                "source_reference": "degree-1",
                "temporal": "valid",
            },
        )

        finding = result.findings[0]
        assert finding.code == "ECTS_COMPLETION_BLOCKED"
        assert finding.metadata["required_known"] is False
        assert finding.metadata["completion_blocked"] is True
        assert finding.metadata["satisfied"] is False


def test_canonical_rule_malformed_legacy_aggregates_do_not_override_structured_evidence():
    result = _canonical_result(
        completed="garbage",
        required="nonsense",
        records=tuple(_record(f"subject-{i}", 30, "completed") for i in range(6)),
        degree_requirement={
            "required_ects": 180,
            "grounded": True,
            "source_reference": "degree-1",
            "temporal": "valid",
        },
    )

    finding = result.findings[0]
    assert finding.code == "ECTS_REQUIREMENT_SATISFIED"
    assert finding.metadata["required"] == 180
    assert finding.metadata["recognized_total"] == 180
    assert finding.metadata["satisfied"] is True


def test_canonical_rule_malformed_legacy_aggregates_without_structure_fail_closed():
    result = _canonical_result(completed="garbage", required="nonsense")

    finding = result.findings[0]
    assert finding.code == "ECTS_COMPLETION_BLOCKED"
    assert finding.metadata["required_known"] is False
    assert finding.metadata["satisfied"] is False


# ── V7-B4: malformed collection-shaped metadata must not leak TypeError; ─────
# ── the rule must degrade to a conservative blocked/unknown result. ───────────


def test_canonical_rule_scalar_records_collection_does_not_crash():
    """A scalar ``records`` value (not a list/tuple) must not raise TypeError."""
    result = _canonical_result(records=7, required=180)
    assert result.status is not None
    finding = result.findings[0]
    assert finding.code in ("ECTS_COMPLETION_BLOCKED", "ECTS_REQUIREMENT_SATISFIED")
    assert finding.metadata["satisfied"] is False


def test_canonical_rule_scalar_double_counted_collection_does_not_crash():
    """A scalar ``double_counted`` value must not raise TypeError."""
    result = _canonical_result(required=180, double_counted=7)
    assert result.status is not None
    finding = result.findings[0]
    assert finding.metadata["satisfied"] is False


def test_canonical_rule_scalar_contradictory_collection_does_not_crash():
    """A scalar ``contradictory`` value must not raise TypeError."""
    result = _canonical_result(required=180, contradictory=7)
    assert result.status is not None
    finding = result.findings[0]
    assert finding.metadata["satisfied"] is False


# ── V8-B1: malformed ECTS conflict metadata must not be treated as no ───────
# ── conflicts, and malformed records cannot confirm completion. ─────────────


def _grounded_complete_records():
    return tuple(_record(f"subject-{i}", 30, "completed") for i in range(6))


def _grounded_degree_requirement():
    return {
        "required_ects": 180,
        "grounded": True,
        "source_reference": "degree-1",
        "temporal": "valid",
    }


def test_canonical_rule_malformed_double_counted_blocks_otherwise_complete():
    """A malformed ``double_counted`` value must not be treated as no
    conflicts; an otherwise fully grounded completion is not confirmed."""
    result = _canonical_result(
        records=_grounded_complete_records(),
        degree_requirement=_grounded_degree_requirement(),
        double_counted=7,
    )
    finding = result.findings[0]
    assert finding.code == "ECTS_COMPLETION_BLOCKED"
    assert finding.metadata["satisfied"] is False
    assert finding.metadata["completion_blocked"] is True
    assert finding.metadata["double_counted_malformed"] is True


def test_canonical_rule_malformed_contradictory_blocks_otherwise_complete():
    """A malformed ``contradictory`` value must not be treated as no
    contradictions; an otherwise fully grounded completion is not confirmed."""
    result = _canonical_result(
        records=_grounded_complete_records(),
        degree_requirement=_grounded_degree_requirement(),
        contradictory=7,
    )
    finding = result.findings[0]
    assert finding.code == "ECTS_COMPLETION_BLOCKED"
    assert finding.metadata["satisfied"] is False
    assert finding.metadata["completion_blocked"] is True
    assert finding.metadata["contradictory_malformed"] is True


def test_canonical_rule_malformed_records_cannot_confirm_completion():
    """A malformed ``records`` value is not authoritative grounded credit
    evidence and cannot confirm a fully grounded completion."""
    result = _canonical_result(
        records=7,
        degree_requirement=_grounded_degree_requirement(),
    )
    finding = result.findings[0]
    assert finding.code == "ECTS_COMPLETION_BLOCKED"
    assert finding.metadata["satisfied"] is False
    assert finding.metadata["records_malformed"] is True
    assert finding.metadata["credit_state_sufficiently_grounded"] is False
# ── V9-B3.1: strict ECTS grounding.  Truthy != grounded. ─────────────────────


def _ungrounded_record(*, grounded="false"):
    return {
        "id": "credits-1",
        "ects": 180,
        "state": "completed",
        "grounded": grounded,
        "source_reference": "rec-1",
        "temporal": "valid",
    }


def _ungrounded_degree_requirement(*, grounded="false"):
    return {
        "required_ects": 180,
        "grounded": grounded,
        "source_reference": "req-1",
        "temporal": "valid",
    }


def test_canonical_rule_truthy_grounded_is_not_grounded():
    """``grounded`` only counts when it is literally ``True``; truthy values
    (``"false"``, ``"true"``, ``1``, ``0``) do not grant grounding."""
    for grounded in ("false", "true", 1, 0):
        result = _canonical_result(
            records=(_ungrounded_record(grounded=grounded),),
            degree_requirement=_ungrounded_degree_requirement(),
        )
        finding = result.findings[0]
        assert finding.code == "ECTS_COMPLETION_BLOCKED", f"grounded={grounded!r}"
        assert finding.metadata["satisfied"] is False, f"grounded={grounded!r}"


def test_canonical_rule_strict_grounded_true_remains_satisfied():
    """The positive regression: literal ``grounded=True`` still satisfies."""
    result = _canonical_result(
        records=(_ungrounded_record(grounded=True),),
        degree_requirement=_ungrounded_degree_requirement(grounded=True),
    )
    finding = result.findings[0]
    assert finding.code == "ECTS_REQUIREMENT_SATISFIED"
    assert finding.metadata["satisfied"] is True


# ── V10-B1/B3: direct helper malformed containers and numeric coercion ───────


def test_direct_helper_malformed_records_container_no_exception():
    """records=7 must not raise and must keep completion unknown."""
    result = check_ects_consistency(
        records=7,
        derive_from_records=True,
    )
    assert result["credit_state_sufficiently_grounded"] is False
    assert result["completion_blocked"] is True
    assert result["satisfied"] is False


def test_direct_helper_malformed_degree_requirement_no_attribute_error():
    """degree_requirement=7 must not raise AttributeError."""
    result = check_ects_consistency(
        records=(),
        degree_requirement=7,
        derive_from_records=True,
    )
    assert result["required_known"] is False
    assert result["satisfied"] is False


def test_direct_helper_numeric_string_legacy_aggregate_is_unknown():
    """completed='abc' must not raise ValueError; malformed numeric metadata
    must produce structured uncertainty instead of a confident total."""
    result = check_ects_consistency(completed="abc", required=180)
    assert result["satisfied"] is False
    assert result["critical_requirement_uncertain"] is True
    assert result.get("numeric_metadata_unknown") is True


def test_direct_helper_numeric_string_is_never_implicitly_converted():
    """'30'/'180' must not be accepted as 30/180."""
    result = check_ects_consistency(completed="30", required="180")
    assert result["satisfied"] is False
    assert result["recognized_total"] == 0
    assert result.get("numeric_metadata_unknown") is True


# ── V15-B1 / V16: strict singular ECTS identities and references ────────────


def _v16_ects_record(identity_field, identity_value, *, source_reference="rec1"):
    return {
        identity_field: identity_value,
        "ects": 6,
        "state": "completed",
        "grounded": True,
        "source_reference": source_reference,
        "temporal": "valid",
    }


@pytest.mark.parametrize("identity_field", ("subject_id", "credit_id", "id"))
@pytest.mark.parametrize("malformed_identity", (["s1"], ("s1",)))
def test_v16_ects_record_identity_collection_cannot_establish_completion(
    identity_field,
    malformed_identity,
):
    result = check_ects_consistency(
        records=(_v16_ects_record(identity_field, malformed_identity),),
        degree_requirement={
            "required_ects": 6,
            "grounded": True,
            "source_reference": "req1",
            "temporal": "valid",
        },
        derive_from_records=True,
    )
    assert result["recognized_total"] == 0
    assert result["completion_determinable"] is False
    assert result["satisfied"] is False


@pytest.mark.parametrize("malformed_reference", (["rec1"], ("rec1",)))
def test_v16_ects_record_source_collection_cannot_ground_credits(
    malformed_reference,
):
    result = check_ects_consistency(
        records=(
            _v16_ects_record(
                "subject_id",
                "s1",
                source_reference=malformed_reference,
            ),
        ),
        degree_requirement={
            "required_ects": 6,
            "grounded": True,
            "source_reference": "req1",
            "temporal": "valid",
        },
        derive_from_records=True,
    )
    assert result["recognized_total"] == 0
    assert result["completion_determinable"] is False
    assert result["satisfied"] is False


@pytest.mark.parametrize("malformed_reference", (["req1"], ("req1",)))
def test_v16_ects_requirement_source_collection_is_not_authoritative(
    malformed_reference,
):
    result = check_ects_consistency(
        records=(_v16_ects_record("subject_id", "s1"),),
        degree_requirement={
            "required_ects": 6,
            "grounded": True,
            "source_reference": malformed_reference,
            "temporal": "valid",
        },
        derive_from_records=True,
    )
    assert result["requirement_grounded"] is False
    assert result["completion_determinable"] is False
    assert result["satisfied"] is False


def test_v16_canonical_ects_collection_identity_never_satisfies_requirement():
    result = _canonical_result(
        records=(_v16_ects_record("subject_id", ["s1"]),),
        degree_requirement={
            "required_ects": 6,
            "grounded": True,
            "source_reference": "req1",
            "temporal": "valid",
        },
    )
    finding = result.findings[0]
    assert finding.code == "ECTS_COMPLETION_BLOCKED"
    assert finding.metadata["completion_determinable"] is False
    assert finding.metadata["satisfied"] is False
