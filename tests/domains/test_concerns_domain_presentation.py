"""Phase 10.25 — Concerns presentation + trace tests.

Presentation preserves semantics without a persona; trace is reference-only
through the shared Phase 10.17 contracts (frozen design §78–§80).
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace

from cmm.domains.concerns.definition import CONCERNS_DOMAIN_ID
from cmm.domains.concerns.presentation import (
    PRESENTATION_STATE_HYPOTHETICAL,
    PRESENTATION_STATE_INTERPRETATION,
    PRESENTATION_STATE_KNOWN_FACT,
    PRESENTATION_STATE_UNKNOWN,
    build_concerns_presentation_policy,
    present_concerns_result,
)
from cmm.domains.concerns.trace import (
    assemble_concerns_trace,
    build_concerns_trace_contribution,
    build_concerns_trace_reference,
    validate_concerns_trace,
)
from cmm.domains.trace_contracts import (
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReferenceKind,
    DomainTraceRole,
    DomainTraceStatus,
    DomainTraceValidationCode,
)

# ── Presentation ─────────────────────────────────────────────────────────────


def test_presentation_policy_is_profile_owned():
    from cmm.domains.concerns.profile import build_concerns_profile

    policy = build_concerns_presentation_policy()
    profile_policy = build_concerns_profile().presentation_policy
    assert policy.detail_level == profile_policy.detail_level
    assert policy.include_uncertainty is True
    assert policy.include_provenance is True
    assert policy.allow_speculation is False


def test_no_persona_semantics_in_policy():
    """No fixed ChatGPT/Claude persona, warmth setting, emoji policy, or
    rhetorical style belongs to the domain presentation layer."""
    policy = build_concerns_presentation_policy()
    for forbidden in ("warmth", "persona", "emoji", "style", "tone"):
        assert not hasattr(policy, forbidden)
    metadata = getattr(policy, "metadata", {}) or {}
    for key in ("warmth", "persona", "emoji_policy"):
        assert key not in dict(metadata) if hasattr(metadata, "keys") else True


def test_presented_states_closed():
    assert PRESENTATION_STATE_KNOWN_FACT == "known_fact"
    assert PRESENTATION_STATE_INTERPRETATION == "interpretation"
    assert PRESENTATION_STATE_HYPOTHETICAL == "hypothetical"
    assert PRESENTATION_STATE_UNKNOWN == "unknown"


def test_presentation_preserves_full_result():
    result = {
        "support_need": "PERSPECTIVE",
        "facts": ("email sent Monday",),
        "interpretations": ("they are avoiding me",),
        "hypotheses": ({"identity": "h1", "statement": "workload explains it"},),
        "fears": ("that I am becoming just another friend",),
        "scenarios": (),
        "uncertainty": ("why they went silent",),
        "reassurance_assessment": "REASSURANCE_PARTIAL",
        "material_concerns": ("one real issue remains",),
        "risk": {"risk_level": "none"},
        "action_state": "ACTION_OPTIONAL",
        "memory_state": {"proposals": (), "persisted": False},
        "permissions": ("resource.read",),
    }
    presented = present_concerns_result(result)
    # facts stay facts; interpretations stay interpretations; hypotheses stay
    # hypothetical; fears/scenarios stay distinct
    fact_items = [item for item in presented["facts"] if isinstance(item, dict)]
    interpretation_items = [
        item for item in presented["interpretations"] if isinstance(item, dict)
    ]
    hypothesis_items = [
        item for item in presented["hypotheses"] if isinstance(item, dict)
    ]
    fear_items = [item for item in presented["fears"] if isinstance(item, dict)]
    assert all(item["presentation_state"] == PRESENTATION_STATE_KNOWN_FACT for item in fact_items)
    assert all(
        item["presentation_state"] == PRESENTATION_STATE_INTERPRETATION
        for item in interpretation_items
    )
    assert all(
        item["presentation_state"] == PRESENTATION_STATE_HYPOTHETICAL
        for item in hypothesis_items
    )
    assert all(item["prediction"] is False for item in fear_items)
    # semantic fields preserved verbatim
    assert presented["reassurance_assessment"] == "REASSURANCE_PARTIAL"
    assert presented["material_concerns"] == ("one real issue remains",)
    assert presented["action_state"] == "ACTION_OPTIONAL"
    assert presented["risk"]["risk_level"] == "none"
    assert presented["memory_state"]["persisted"] is False
    assert presented["permissions"] == ("resource.read",)
    assert presented["certainty_amplified"] is False
    json.dumps(presented, allow_nan=False)


def test_presentation_cannot_upgrade_uncertainty_or_adopt_action():
    result = {
        "uncertainty": ("unknown cause",),
        "action_state": "NO_ACTION_NEEDED",
        "support_need": "UNCLEAR",
        "reassurance_assessment": "INSUFFICIENT_BASIS",
    }
    presented = present_concerns_result(result)
    assert presented["uncertainty"] == ("unknown cause",)
    assert presented["action_state"] == "NO_ACTION_NEEDED"
    assert presented["support_need"] == "UNCLEAR"
    assert presented["reassurance_assessment"] == "INSUFFICIENT_BASIS"
    assert presented["conclusion_presented"] is False


def test_presentation_malformed_input_fails_closed():
    presented = present_concerns_result("not-a-mapping")
    assert presented["unresolved"] is True
    assert presented["presentation_state"] == PRESENTATION_STATE_UNKNOWN
    json.dumps(presented, allow_nan=False)


def test_presentation_does_not_turn_inference_into_user_fact():
    result = {
        "interpretations": ("they are angry at me",),
        "fears": ("I will be replaced",),
    }
    presented = present_concerns_result(result)
    for item in presented["interpretations"]:
        assert item.get("user_fact") is not True
    for item in presented["fears"]:
        assert item.get("prediction") is False


def test_presentation_input_not_mutated():
    result = {
        "facts": ["f"],
        "interpretations": ["i"],
        "hypotheses": [{"identity": "h"}],
        "uncertainty": ["u"],
    }
    snapshot = copy.deepcopy(result)
    present_concerns_result(result)
    assert result == snapshot


def test_presentation_section_order_is_semantic():
    result = {
        "support_need": "PERSPECTIVE",
        "lived_impact": "sleep affected",
        "perspective": {"available": True},
        "epistemic_distinctions": ("fact vs interpretation",),
        "uncertainty": ("cause unknown",),
        "reassurance_assessment": "REASSURANCE_PARTIAL",
        "material_concerns": ("one issue",),
        "action_state": "ACTION_OPTIONAL",
        "actual_concern": "manager silence",
    }
    presented = present_concerns_result(result)
    expected_order = (
        "actual_concern",
        "lived_impact",
        "perspective",
        "epistemic_distinctions",
        "uncertainty",
        "reassurance_material_concern",
        "proportional_action",
    )
    assert tuple(presented["section_order"]) == expected_order


# ── Trace ────────────────────────────────────────────────────────────────────

NOW = __import__("datetime").datetime(2026, 8, 21, 15, 0, tzinfo=__import__("datetime").timezone.utc)

_CALLER_KINDS = (
    (DomainTraceReferenceKind.RESOURCE_RESOLUTION, "res:1"),
    (DomainTraceReferenceKind.PROFILE, "profile:1"),
    (DomainTraceReferenceKind.RULE_RESULT, "rule:1"),
    (DomainTraceReferenceKind.PERMISSION_DECISION, "perm:1"),
    (DomainTraceReferenceKind.APPROVAL_REQUEST, "approval-req:1"),
    (DomainTraceReferenceKind.APPROVAL_DECISION, "approval-dec:1"),
    (DomainTraceReferenceKind.OPERATION_RESULT, "op:1"),
    (DomainTraceReferenceKind.WORKFLOW_RESULT, "wf:1"),
)


def _ref(ref_id, kind):
    return build_concerns_trace_reference(ref_id=ref_id, kind=kind)


def test_reference_wrapper_uses_supplied_kind():
    ref = _ref("res:1", DomainTraceReferenceKind.RESOURCE_RESOLUTION)
    assert ref.ref_id == "res:1"
    assert str(ref.domain_id) == "domain:concerns"


def test_contribution_adds_exactly_one_domain_result():
    contribution = build_concerns_trace_contribution(
        domain_result_id="dr:1",
        references=(_ref("op:1", DomainTraceReferenceKind.OPERATION_RESULT),),
    )
    assert isinstance(contribution, DomainTraceContribution)
    assert contribution.role is DomainTraceRole.PRIMARY
    kinds = [r.kind for r in contribution.references]
    assert kinds.count(DomainTraceReferenceKind.DOMAIN_RESULT) == 1


def test_assemble_preserves_global_ids_and_support_need_metadata():
    trace = assemble_concerns_trace(
        request_id="req1",
        resolution_context_id="resolution-context:1",
        resolution_result_id="resolution-result:1",
        composition_id="composition:1",
        domain_result_id="domain-result:1",
        started_at=NOW,
        completed_at=NOW.replace(second=1),
        references=tuple(_ref(ref_id, kind) for kind, ref_id in _CALLER_KINDS),
    )
    assert trace.references.resolution_context_id == "resolution-context:1"
    assert trace.domain_results[0].result_id == "domain-result:1"
    assert trace.status is DomainTraceStatus.COMPLETED


def test_trace_is_reference_only_no_chain_of_thought():
    trace = assemble_concerns_trace(
        request_id="req2",
        resolution_context_id="rc:1",
        resolution_result_id="rr:1",
        composition_id="c:1",
        domain_result_id="dr:1",
        started_at=NOW,
        completed_at=NOW.replace(second=1),
    )
    serialized = json.dumps(trace.to_dict(), allow_nan=False).lower()
    assert "chain" not in serialized
    assert "private" not in serialized


def test_trace_validates_against_inventory():
    from cmm.domains.trace_contracts import DomainTraceReferenceInventory

    trace = assemble_concerns_trace(
        request_id="req3",
        resolution_context_id="rc:2",
        resolution_result_id="rr:2",
        composition_id="c:2",
        domain_result_id="dr:2",
        started_at=NOW,
        completed_at=NOW.replace(second=1),
    )
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain=CONCERNS_DOMAIN_ID,
        expected_supporting_domains=(),
        resolution_result_domains=DomainTraceDomainSelection("rr:2", CONCERNS_DOMAIN_ID),
        composition_domains=DomainTraceDomainSelection("c:2", CONCERNS_DOMAIN_ID),
    )
    result = validate_concerns_trace(trace=trace, inventory=inventory)
    assert result.valid is True

    extra = _ref("ghost:1", DomainTraceReferenceKind.FINDING)
    bad_inventory = replace(inventory, references=(*inventory.references, extra))
    bad_result = validate_concerns_trace(trace=trace, inventory=bad_inventory)
    assert bad_result.valid is False
    assert DomainTraceValidationCode.MISSING_REFERENCE in bad_result.codes
