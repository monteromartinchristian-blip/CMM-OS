"""Tests for Phase 10.11 – Domain Profile Composition (Tasks 6, 7, 8)."""

from __future__ import annotations

from typing import runtime_checkable

from cmm.domains.enums import (
    DomainProfileDecisionCode,
    DomainProfileSource,
    DomainReasoningDepth,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.profile_composition import (
    DefaultDomainProfileComposer,
    DomainProfileComposer,
    _CompositionState,
    _ordered_intersection,
    _ordered_union,
    merge_memory_policy,
    merge_presentation_policy,
    merge_production_policy,
    merge_question_policy,
    merge_temporal_policy,
)
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileDefinition,
    DomainProfileOverlay,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)


def _global(**overrides) -> DomainProfileDefinition:
    defaults = {
        "id": "global-1",
        "domain_id": DomainId("general"),
        "profile_name": "GeneralProfile",
    }
    defaults.update(overrides)
    return DomainProfileDefinition(**defaults)


def _primary(**overrides) -> DomainProfileDefinition:
    defaults = {
        "id": "primary-1",
        "domain_id": DomainId("health"),
        "profile_name": "HealthProfile",
    }
    defaults.update(overrides)
    return DomainProfileDefinition(**defaults)


def _supporting(**overrides) -> DomainProfileDefinition:
    defaults = {
        "id": "supporting-1",
        "domain_id": DomainId("relationship"),
        "profile_name": "RelationshipProfile",
    }
    defaults.update(overrides)
    return DomainProfileDefinition(**defaults)


def _overlay(**overrides) -> DomainProfileOverlay:
    defaults = {
        "id": "overlay-1",
        "source": DomainProfileSource.RISK,
        "source_id": "high",
    }
    defaults.update(overrides)
    return DomainProfileOverlay(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# Core pure helpers
# ═══════════════════════════════════════════════════════════════════════════════


def test_ordered_union_preserves_first_appearance_order():
    assert _ordered_union(("b", "a"), ("c", "a", "d")) == ("b", "a", "c", "d")


def test_ordered_intersection_preserves_left_order():
    assert _ordered_intersection(("c", "a", "b"), ("a", "c")) == ("c", "a")


# ═══════════════════════════════════════════════════════════════════════════════
# Composer protocol
# ═══════════════════════════════════════════════════════════════════════════════


def test_domain_profile_composer_is_runtime_checkable_protocol():
    assert runtime_checkable(DomainProfileComposer) is DomainProfileComposer
    composer = DefaultDomainProfileComposer()
    assert isinstance(composer, DomainProfileComposer)


# ═══════════════════════════════════════════════════════════════════════════════
# Required / optional / prohibited rule interactions
# ═══════════════════════════════════════════════════════════════════════════════


def test_required_rules_ordered_union_across_sources():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(required_rules=("r1",)),
        primary_profile=_primary(required_rules=("r2",)),
        supporting_profiles=(_supporting(required_rules=("r3",)),),
        overlays=(),
        request_permissions=None,
    )
    assert result.profile.required_rules == ("r1", "r2", "r3")


def test_optional_rules_exclude_required_and_prohibited():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(
            required_rules=("r1",),
            prohibited_rules=("p1",),
            optional_rules=("o1", "r1", "p1"),
        ),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(),
        request_permissions=None,
    )
    assert result.profile.optional_rules == ("o1",)


def test_prohibited_rules_prevail_over_optional():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(optional_rules=("o1",), prohibited_rules=("o1",)),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert "o1" not in result.profile.optional_rules
    assert "o1" in result.profile.prohibited_rules


def test_global_mandatory_and_prohibited_conflict_is_blocking():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(required_rules=("r1",), prohibited_rules=("r1",)),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert any(c.blocking for c in result.conflicts)
    assert [c.code for c in result.conflicts] == ["GLOBAL_MANDATORY_PROHIBITED"]
    assert any(
        d.code == DomainProfileDecisionCode.CONFLICT_RECORDED and d.blocking
        for d in result.decisions
    )


def test_non_global_required_and_prohibited_conflict_is_non_blocking():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(),
        primary_profile=_primary(required_rules=("r1",), prohibited_rules=("r1",)),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert any(not c.blocking for c in result.conflicts)
    assert [c.code for c in result.conflicts] == ["REQUIRED_AND_PROHIBITED_RULE"]
    assert any(
        d.code == DomainProfileDecisionCode.PROHIBITED_RULE_PREVAILED
        for d in result.decisions
    )


def test_overlay_prohibited_rules_are_unioned():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(_overlay(prohibited_rules=("p1",)),),
        request_permissions=(),
    )
    assert result.profile.prohibited_rules == ("p1",)


# ═══════════════════════════════════════════════════════════════════════════════
# Allowed / prohibited inference interactions
# ═══════════════════════════════════════════════════════════════════════════════


def test_allowed_inferences_none_is_unconstrained():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert result.profile.allowed_inferences is None


def test_allowed_inferences_restrictive_intersection():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(allowed_inferences=("i1", "i2")),
        primary_profile=_primary(allowed_inferences=("i2", "i3")),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert result.profile.allowed_inferences == ("i2",)


def test_prohibited_inferences_remove_allowed_and_record_conflict():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(allowed_inferences=("i1", "i2")),
        primary_profile=_primary(prohibited_inferences=("i1",)),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert result.profile.allowed_inferences == ("i2",)
    assert "i1" in result.profile.prohibited_inferences
    assert [c.code for c in result.conflicts] == ["ALLOWED_AND_PROHIBITED_INFERENCE"]
    assert any(
        d.code == DomainProfileDecisionCode.INFERENCE_PROHIBITED
        for d in result.decisions
    )


def test_global_prohibited_inference_cannot_be_reactivated_by_overlay():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(prohibited_inferences=("i1",)),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(_overlay(allowed_inferences=("i1", "i2")),),
        request_permissions=(),
    )
    assert "i1" not in result.profile.allowed_inferences
    assert "i2" in result.profile.allowed_inferences


# ═══════════════════════════════════════════════════════════════════════════════
# Resource allowed / priority / prohibited interactions
# ═══════════════════════════════════════════════════════════════════════════════


def test_resource_allowed_kinds_restrictive_intersection():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(),
        primary_profile=_primary(allowed_resource_kinds=("a", "b")),
        supporting_profiles=(),
        overlays=(_overlay(allowed_resource_kinds=("a",)),),
        request_permissions=(),
    )
    assert result.profile.allowed_resource_kinds == ("a",)


def test_resource_priority_kinds_filtered_to_allowed_and_not_prohibited():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(),
        primary_profile=_primary(
            allowed_resource_kinds=("a", "b"),
            priority_resource_kinds=("a", "b"),
        ),
        supporting_profiles=(),
        overlays=(_overlay(prohibited_resource_kinds=("b",)),),
        request_permissions=(),
    )
    assert result.profile.priority_resource_kinds == ("a",)


def test_overlay_cannot_re_enable_globally_prohibited_resource():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(prohibited_resource_kinds=("a",)),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(_overlay(allowed_resource_kinds=("a", "b")),),
        request_permissions=(),
    )
    assert "a" not in result.profile.allowed_resource_kinds
    assert "b" in result.profile.allowed_resource_kinds


# ═══════════════════════════════════════════════════════════════════════════════
# Confidence and reasoning depth
# ═══════════════════════════════════════════════════════════════════════════════


def test_minimum_confidence_never_decreases():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(minimum_confidence=0.6),
        primary_profile=_primary(minimum_confidence=0.3),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert result.profile.minimum_confidence == 0.6
    assert any(
        d.code == DomainProfileDecisionCode.CONFIDENCE_RAISED for d in result.decisions
    )


def test_reasoning_depth_most_restrictive_lower_depth_wins():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(reasoning_depth=DomainReasoningDepth.SHALLOW),
        primary_profile=_primary(reasoning_depth=DomainReasoningDepth.EXHAUSTIVE),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert result.profile.reasoning_depth == DomainReasoningDepth.SHALLOW


# ═══════════════════════════════════════════════════════════════════════════════
# Questions, escalation, actions
# ═══════════════════════════════════════════════════════════════════════════════


def test_maximum_questions_only_narrows():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(maximum_questions=10),
        primary_profile=_primary(maximum_questions=3),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert result.profile.maximum_questions == 3


def test_escalation_rules_are_unioned_and_never_removed():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(escalation_rules=("e1",)),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(_overlay(escalation_rules=("e2",)),),
        request_permissions=(),
    )
    assert result.profile.escalation_rules == ("e1", "e2")


def test_prohibited_actions_ordered_union_and_prevail():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(prohibited_actions=("act1",)),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(_overlay(prohibited_actions=("act2",)),),
        request_permissions=(),
    )
    assert result.profile.prohibited_actions == ("act1", "act2")


# ═══════════════════════════════════════════════════════════════════════════════
# Permissions only narrow; explicit deny wins
# ═══════════════════════════════════════════════════════════════════════════════


def test_permissions_unconstrained_when_no_source_restricts():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(),
        request_permissions=None,
    )
    assert result.profile.permissions is None


def test_permissions_only_narrow_across_sources():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(permissions=("read", "write")),
        primary_profile=_primary(permissions=("read",)),
        supporting_profiles=(),
        overlays=(),
        request_permissions=None,
    )
    assert result.profile.permissions == ("read",)


def test_explicit_empty_permissions_deny_all():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(permissions=()),
        primary_profile=_primary(permissions=("read",)),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert result.profile.permissions == ()


def test_request_permissions_narrow_when_non_empty():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(permissions=("read", "write")),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(),
        request_permissions=("read",),
    )
    assert result.profile.permissions == ("read",)


def test_request_permissions_empty_tuple_denies_all():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(permissions=("read", "write")),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert result.profile.permissions == ()


def test_request_permissions_none_is_unconstrained():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(permissions=("read", "write")),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(),
        request_permissions=None,
    )
    assert result.profile.permissions == ("read", "write")


def test_permissions_never_expanded_by_overlay():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(permissions=("read",)),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(_overlay(permissions=("read", "write")),),
        request_permissions=None,
    )
    assert result.profile.permissions == ("read",)


def test_deny_permission_prevails_over_explicit_grant_same_source():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(permissions=("read", "write")),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(_overlay(permissions=("read", "write", "deny:write")),),
        request_permissions=None,
    )
    assert "write" not in result.profile.permissions
    assert "read" in result.profile.permissions
    assert "deny:write" in result.profile.permissions


def test_deny_permission_prevails_across_sources():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(permissions=("read", "write")),
        primary_profile=_primary(permissions=("read", "write", "deny:write")),
        supporting_profiles=(),
        overlays=(),
        request_permissions=None,
    )
    assert result.profile.permissions == ("read", "deny:write")


def test_deny_permission_cannot_be_regranted_by_later_overlay():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(permissions=("read", "write")),
        primary_profile=_primary(permissions=("read", "write", "deny:write")),
        supporting_profiles=(),
        overlays=(
            _overlay(id="ov-1", permissions=("read", "write", "deny:write")),
            _overlay(id="ov-2", permissions=("read", "write")),
        ),
        request_permissions=(),
    )
    assert "write" not in result.profile.permissions


def test_deny_permission_from_request_permissions_prevails():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(permissions=("read", "write")),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(),
        request_permissions=("read", "write", "deny:write"),
    )
    assert "write" not in result.profile.permissions
    assert "read" in result.profile.permissions


# ═══════════════════════════════════════════════════════════════════════════════
# Overlay ordering (source precedence, priority, source_id, id)
# ═══════════════════════════════════════════════════════════════════════════════


def test_overlays_applied_in_source_precedence_then_priority_order():
    composer = DefaultDomainProfileComposer()
    overlay_low_precedence = _overlay(
        id="ov-workflow",
        source=DomainProfileSource.WORKFLOW,
        maximum_questions=8,
    )
    overlay_high_precedence = _overlay(
        id="ov-explicit",
        source=DomainProfileSource.EXPLICIT_REQUEST,
        maximum_questions=2,
    )
    result = composer.compose(
        global_profile=_global(),
        primary_profile=_primary(maximum_questions=10),
        supporting_profiles=(),
        overlays=(overlay_high_precedence, overlay_low_precedence),
        request_permissions=(),
    )
    assert result.profile.maximum_questions == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Typed policy merges
# ═══════════════════════════════════════════════════════════════════════════════


def test_merge_question_policy_maximum_questions_takes_minimum():
    current = DomainQuestionPolicy(maximum_questions=10)
    incoming = DomainQuestionPolicy(maximum_questions=5)
    merged, changes = merge_question_policy(current, incoming)
    assert merged.maximum_questions == 5
    assert changes


def test_merge_question_policy_capability_booleans_and():
    current = DomainQuestionPolicy(allow_follow_up=True)
    incoming = DomainQuestionPolicy(allow_follow_up=False)
    merged, _ = merge_question_policy(current, incoming)
    assert merged.allow_follow_up is False


def test_merge_question_policy_safety_booleans_or():
    current = DomainQuestionPolicy(require_deduplication=False)
    incoming = DomainQuestionPolicy(require_deduplication=True)
    merged, _ = merge_question_policy(current, incoming)
    assert merged.require_deduplication is True


def test_merge_question_policy_none_incoming_is_no_op():
    current = DomainQuestionPolicy(maximum_questions=5)
    merged, changes = merge_question_policy(current, None)
    assert merged is current
    assert changes == ()


def test_merge_presentation_policy_detail_level_restrictive():
    current = DomainPresentationPolicy(detail_level="exhaustive")
    incoming = DomainPresentationPolicy(detail_level="minimal")
    merged, _ = merge_presentation_policy(current, incoming)
    assert merged.detail_level == "minimal"


def test_merge_presentation_policy_allow_speculation_and():
    current = DomainPresentationPolicy(allow_speculation=True)
    incoming = DomainPresentationPolicy(allow_speculation=False)
    merged, _ = merge_presentation_policy(current, incoming)
    assert merged.allow_speculation is False


def test_merge_memory_policy_capability_booleans_and():
    current = DomainMemoryPolicy(allow_cross_domain=True)
    incoming = DomainMemoryPolicy(allow_cross_domain=False)
    merged, _ = merge_memory_policy(current, incoming)
    assert merged.allow_cross_domain is False


def test_memory_retention_none_is_most_restrictive():
    current = DomainMemoryPolicy(retention_scope="long_term")
    incoming = DomainMemoryPolicy(retention_scope="none")
    merged, _ = merge_memory_policy(current, incoming)
    assert merged.retention_scope == "none"


def test_memory_retention_turn_restricts_session():
    current = DomainMemoryPolicy(retention_scope="session")
    incoming = DomainMemoryPolicy(retention_scope="turn")
    merged, _ = merge_memory_policy(current, incoming)
    assert merged.retention_scope == "turn"


def test_memory_retention_cannot_expand():
    current = DomainMemoryPolicy(retention_scope="short_term")
    incoming = DomainMemoryPolicy(retention_scope="long_term")
    merged, _ = merge_memory_policy(current, incoming)
    assert merged.retention_scope == "short_term"


def test_merge_memory_policy_sensitivity_limit_restrictive():
    from cmm.cognitive.enums import SensitivityLevel

    current = DomainMemoryPolicy(sensitivity_limit=SensitivityLevel.RESTRICTED)
    incoming = DomainMemoryPolicy(sensitivity_limit=SensitivityLevel.PUBLIC)
    merged, _ = merge_memory_policy(current, incoming)
    assert merged.sensitivity_limit == SensitivityLevel.PUBLIC


def test_merge_temporal_policy_require_flags_or():
    current = DomainTemporalPolicy(require_temporal_provenance=False)
    incoming = DomainTemporalPolicy(require_temporal_provenance=True)
    merged, _ = merge_temporal_policy(current, incoming)
    assert merged.require_temporal_provenance is True


def test_merge_temporal_policy_maximum_age_seconds_minimum():
    current = DomainTemporalPolicy(maximum_age_seconds=1000)
    incoming = DomainTemporalPolicy(maximum_age_seconds=100)
    merged, _ = merge_temporal_policy(current, incoming)
    assert merged.maximum_age_seconds == 100


def test_merge_production_policy_external_action_and():
    current = DomainProductionPolicy(allow_external_action=True)
    incoming = DomainProductionPolicy(allow_external_action=False)
    merged, _ = merge_production_policy(current, incoming)
    assert merged.allow_external_action is False


def test_merge_production_policy_require_review_or():
    current = DomainProductionPolicy(require_review=False)
    incoming = DomainProductionPolicy(require_review=True)
    merged, _ = merge_production_policy(current, incoming)
    assert merged.require_review is True


def test_merge_production_policy_maximum_output_items_minimum():
    current = DomainProductionPolicy(maximum_output_items=10)
    incoming = DomainProductionPolicy(maximum_output_items=4)
    merged, _ = merge_production_policy(current, incoming)
    assert merged.maximum_output_items == 4


def test_typed_policy_merge_produces_modification_records():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(
            question_policy=DomainQuestionPolicy(maximum_questions=10)
        ),
        primary_profile=_primary(
            question_policy=DomainQuestionPolicy(maximum_questions=4)
        ),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert result.profile.question_policy.maximum_questions == 4
    assert any(
        m.field == "question_policy.maximum_questions" for m in result.modifications
    )
    assert any(
        d.code == DomainProfileDecisionCode.POLICY_RESTRICTED for d in result.decisions
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Result shape and profile identity fields
# ═══════════════════════════════════════════════════════════════════════════════


def test_composition_result_records_supporting_domains_and_profile_names():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(),
        primary_profile=_primary(),
        supporting_profiles=(_supporting(),),
        overlays=(),
        request_permissions=(),
    )
    assert result.profile.primary_domain == DomainId("health")
    assert result.profile.supporting_domains == (DomainId("relationship"),)
    assert result.profile.profile_names == (
        "GeneralProfile",
        "HealthProfile",
        "RelationshipProfile",
    )


def test_composition_result_metadata_defaults_to_empty_mapping():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert dict(result.metadata) == {}


def test_composition_no_op_produces_no_modifications_or_decisions_for_matching_defaults():
    composer = DefaultDomainProfileComposer()
    result = composer.compose(
        global_profile=_global(),
        primary_profile=_primary(),
        supporting_profiles=(),
        overlays=(),
        request_permissions=(),
    )
    assert result.conflicts == ()
    assert result.rejections == ()


def test_composer_initial_state_uses_approved_defaults():
    state = _CompositionState()
    assert state.reasoning_depth == DomainReasoningDepth.EXHAUSTIVE
    assert state.maximum_questions == 16
