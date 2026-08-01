"""Tests for Phase 10.11 – Domain Profile contracts (Tasks 2-4)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from cmm.domains.enums import (
    DomainProfileConflictSeverity,
    DomainProfileDecisionCode,
    DomainProfileResolutionStatus,
    DomainProfileSource,
    DomainReasoningDepth,
)
from cmm.domains.errors import (
    DomainProfileContractError,
    DomainProfileSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileCompositionResult,
    DomainProfileConflict,
    DomainProfileDecision,
    DomainProfileDefinition,
    DomainProfileDraft,
    DomainProfileModification,
    DomainProfileOverlay,
    DomainProfileRejection,
    DomainProfileResolution,
    DomainProfileResolutionRequest,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
    ResolvedDomainProfile,
)

NOW = datetime.now(timezone.utc)


def _resolved_profile(**overrides):
    kwargs = {
        "id": "rp-1",
        "primary_domain": DomainId("health"),
        "supporting_domains": (),
        "profile_names": ("HealthProfile",),
        "required_rules": (),
        "optional_rules": (),
        "prohibited_rules": (),
        "allowed_resource_kinds": None,
        "priority_resource_kinds": (),
        "prohibited_resource_kinds": (),
        "minimum_confidence": 0.5,
        "reasoning_depth": DomainReasoningDepth.STANDARD,
        "allowed_inferences": None,
        "prohibited_inferences": (),
        "maximum_questions": 5,
        "escalation_rules": (),
        "prohibited_actions": (),
        "question_policy": DomainQuestionPolicy(),
        "presentation_policy": DomainPresentationPolicy(),
        "memory_policy": DomainMemoryPolicy(),
        "temporal_policy": DomainTemporalPolicy(),
        "production_policy": DomainProductionPolicy(),
        "permissions": None,
        "modifications": (),
        "trace_id": "trace-1",
        "resolved_at": NOW,
    }
    kwargs.update(overrides)
    return ResolvedDomainProfile(**kwargs)


# ── Typed policies ──────────────────────────────────────────────────────────


class TestDomainQuestionPolicy:
    def test_defaults_are_all_none(self):
        p = DomainQuestionPolicy()
        assert p.maximum_questions is None
        assert p.allow_follow_up is None
        assert p.metadata == {}

    def test_rejects_non_positive_maximum_questions(self):
        with pytest.raises(DomainProfileContractError):
            DomainQuestionPolicy(maximum_questions=0)

    def test_rejects_bool_for_maximum_questions(self):
        with pytest.raises(DomainProfileContractError):
            DomainQuestionPolicy(maximum_questions=True)

    def test_roundtrip(self):
        p = DomainQuestionPolicy(maximum_questions=3, allow_follow_up=True)
        assert DomainQuestionPolicy.from_dict(p.to_dict()) == p

    def test_from_dict_rejects_unknown_field(self):
        with pytest.raises(DomainProfileSerializationError):
            DomainQuestionPolicy.from_dict({"bogus": 1})


class TestDomainPresentationPolicy:
    def test_detail_level_must_be_closed_set(self):
        with pytest.raises(DomainProfileContractError):
            DomainPresentationPolicy(detail_level="ultra")

    def test_valid_detail_level(self):
        p = DomainPresentationPolicy(detail_level="minimal")
        assert p.detail_level == "minimal"

    def test_roundtrip(self):
        p = DomainPresentationPolicy(detail_level="standard", include_uncertainty=True)
        assert DomainPresentationPolicy.from_dict(p.to_dict()) == p


class TestDomainMemoryPolicy:
    def test_retention_scope_must_be_closed_set(self):
        with pytest.raises(DomainProfileContractError):
            DomainMemoryPolicy(retention_scope="forever")

    def test_sensitivity_limit_coerced_from_string(self):
        p = DomainMemoryPolicy(sensitivity_limit="sensitive")
        from cmm.cognitive.enums import SensitivityLevel

        assert p.sensitivity_limit == SensitivityLevel.SENSITIVE

    def test_invalid_sensitivity_limit(self):
        with pytest.raises(DomainProfileContractError):
            DomainMemoryPolicy(sensitivity_limit="not-a-level")

    def test_roundtrip(self):
        p = DomainMemoryPolicy(allow_read=True, retention_scope="session")
        assert DomainMemoryPolicy.from_dict(p.to_dict()) == p

    def test_invalid_permanent_retention_rejected(self):
        with pytest.raises(DomainProfileContractError):
            DomainMemoryPolicy(retention_scope="permanent")


class TestDomainTemporalPolicy:
    def test_negative_maximum_age_rejected(self):
        with pytest.raises(DomainProfileContractError):
            DomainTemporalPolicy(maximum_age_seconds=-1)

    def test_zero_maximum_age_allowed(self):
        p = DomainTemporalPolicy(maximum_age_seconds=0)
        assert p.maximum_age_seconds == 0

    def test_roundtrip(self):
        p = DomainTemporalPolicy(
            require_current_information=True, maximum_age_seconds=60
        )
        assert DomainTemporalPolicy.from_dict(p.to_dict()) == p


class TestDomainProductionPolicy:
    def test_non_positive_maximum_output_items_rejected(self):
        with pytest.raises(DomainProfileContractError):
            DomainProductionPolicy(maximum_output_items=0)

    def test_roundtrip(self):
        p = DomainProductionPolicy(allow_draft=True, maximum_output_items=2)
        assert DomainProductionPolicy.from_dict(p.to_dict()) == p


# ── DomainProfileDefinition ─────────────────────────────────────────────────


class TestDomainProfileDefinition:
    def test_definition_defaults_are_unconstrained(self):
        d = DomainProfileDefinition(
            id="def-1", domain_id=DomainId("health"), profile_name="HealthProfile"
        )
        assert d.minimum_confidence == 0.0
        assert d.reasoning_depth == DomainReasoningDepth.EXHAUSTIVE
        assert d.maximum_questions == 16
        assert d.allowed_resource_kinds is None
        assert d.allowed_inferences is None

    def test_priority_resource_kinds_must_be_subset_of_allowed(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="def-1",
                domain_id=DomainId("health"),
                profile_name="HealthProfile",
                allowed_resource_kinds=("doc",),
                priority_resource_kinds=("note",),
            )

    def test_priority_resource_kinds_disjoint_from_prohibited(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="def-1",
                domain_id=DomainId("health"),
                profile_name="HealthProfile",
                priority_resource_kinds=("doc",),
                prohibited_resource_kinds=("doc",),
            )

    def test_required_and_prohibited_rules_overlap_allowed_at_contract_level(self):
        # The design doc defers this conflict to resolution time.
        d = DomainProfileDefinition(
            id="def-1",
            domain_id=DomainId("health"),
            profile_name="HealthProfile",
            required_rules=("r1",),
            prohibited_rules=("r1",),
        )
        assert "r1" in d.required_rules
        assert "r1" in d.prohibited_rules

    def test_minimum_confidence_out_of_range_rejected(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="def-1",
                domain_id=DomainId("health"),
                profile_name="HealthProfile",
                minimum_confidence=1.5,
            )

    def test_maximum_questions_must_be_positive(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="def-1",
                domain_id=DomainId("health"),
                profile_name="HealthProfile",
                maximum_questions=0,
            )

    def test_nested_policy_from_mapping(self):
        d = DomainProfileDefinition(
            id="def-1",
            domain_id=DomainId("health"),
            profile_name="HealthProfile",
            question_policy={"maximum_questions": 4},
        )
        assert d.question_policy.maximum_questions == 4

    def test_roundtrip(self):
        d = DomainProfileDefinition(
            id="def-1",
            domain_id=DomainId("health"),
            profile_name="HealthProfile",
            required_rules=("r1",),
            allowed_resource_kinds=("doc", "note"),
            priority_resource_kinds=("doc",),
        )
        assert DomainProfileDefinition.from_dict(d.to_dict()) == d

    def test_from_dict_missing_required_field(self):
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileDefinition.from_dict({"id": "def-1"})

    def test_is_frozen(self):
        d = DomainProfileDefinition(
            id="def-1", domain_id=DomainId("health"), profile_name="HealthProfile"
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.id = "other"


# ── DomainProfileOverlay ─────────────────────────────────────────────────────


class TestDomainProfileOverlay:
    def test_all_optional_fields_default_none(self):
        o = DomainProfileOverlay(
            id="ov-1", source=DomainProfileSource.WORKFLOW, source_id="wf-1"
        )
        assert o.required_rules is None
        assert o.minimum_confidence is None
        assert o.reasoning_depth is None

    def test_source_coerced_from_string(self):
        o = DomainProfileOverlay(id="ov-1", source="operation", source_id="op-1")
        assert o.source == DomainProfileSource.OPERATION

    def test_invalid_source_rejected(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(id="ov-1", source="not-a-source")

    def test_priority_resource_kinds_subset_only_checked_when_both_present(self):
        o = DomainProfileOverlay(
            id="ov-1",
            source=DomainProfileSource.RISK,
            source_id="high",
            priority_resource_kinds=("doc",),
        )
        assert o.priority_resource_kinds == ("doc",)

    def test_priority_resource_kinds_subset_violation(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(
                id="ov-1",
                source=DomainProfileSource.RISK,
                source_id="high",
                allowed_resource_kinds=("doc",),
                priority_resource_kinds=("note",),
            )

    def test_roundtrip(self):
        o = DomainProfileOverlay(
            id="ov-1",
            source=DomainProfileSource.WORKFLOW,
            source_id="wf-1",
            minimum_confidence=0.5,
            reasoning_depth=DomainReasoningDepth.DEEP,
            question_policy=DomainQuestionPolicy(maximum_questions=2),
        )
        assert DomainProfileOverlay.from_dict(o.to_dict()) == o

    def test_negative_priority_rejected(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(
                id="ov-1",
                source=DomainProfileSource.RISK,
                source_id="high",
                priority=-1,
            )

    def _assert_source_requires_id(self, source):
        with pytest.raises(DomainProfileContractError, match="source_id"):
            DomainProfileOverlay(id="ov-1", source=source)

    def test_primary_overlay_requires_source_id(self):
        self._assert_source_requires_id(DomainProfileSource.PRIMARY_DOMAIN)

    def test_supporting_overlay_requires_source_id(self):
        self._assert_source_requires_id(DomainProfileSource.SUPPORTING_DOMAIN)

    def test_workflow_overlay_requires_source_id(self):
        self._assert_source_requires_id(DomainProfileSource.WORKFLOW)

    def test_operation_overlay_requires_source_id(self):
        self._assert_source_requires_id(DomainProfileSource.OPERATION)

    def test_risk_overlay_requires_source_id(self):
        self._assert_source_requires_id(DomainProfileSource.RISK)

    def test_actor_overlay_requires_source_id(self):
        self._assert_source_requires_id(DomainProfileSource.ACTOR)

    def test_autonomy_overlay_requires_source_id(self):
        self._assert_source_requires_id(DomainProfileSource.AUTONOMY)

    def test_explicit_request_overlay_requires_source_id(self):
        self._assert_source_requires_id(DomainProfileSource.EXPLICIT_REQUEST)

    def test_global_overlay_may_omit_source_id(self):
        overlay = DomainProfileOverlay(
            id="ov-1", source=DomainProfileSource.GLOBAL_POLICY
        )
        assert overlay.source_id is None

    @pytest.mark.parametrize("bad_source_id", ["", "   ", 1, object()])
    def test_contextual_source_id_must_be_non_empty_string(self, bad_source_id):
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(
                id="ov-1",
                source=DomainProfileSource.WORKFLOW,
                source_id=bad_source_id,
            )


# ── DomainProfileResolutionRequest ──────────────────────────────────────────


class TestDomainProfileResolutionRequest:
    def test_primary_domain_must_not_be_in_supporting(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileResolutionRequest(
                id="req-1",
                primary_domain=DomainId("health"),
                supporting_domains=(DomainId("health"),),
            )

    def test_roundtrip(self):
        r = DomainProfileResolutionRequest(
            id="req-1",
            primary_domain=DomainId("health"),
            supporting_domains=(DomainId("sport"),),
            workflow_ids=("w1",),
        )
        assert DomainProfileResolutionRequest.from_dict(r.to_dict()) == r


# ── DomainProfileModification / Conflict / Rejection / Decision ────────────


class TestDomainProfileModification:
    def test_roundtrip(self):
        m = DomainProfileModification(
            field="minimum_confidence",
            source=DomainProfileSource.RISK,
            source_id="risk-1",
            operation="raise",
            previous_value=0.1,
            new_value=0.5,
        )
        assert DomainProfileModification.from_dict(m.to_dict()) == m

    def test_rejects_non_json_safe_value(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileModification(
                field="x",
                source=DomainProfileSource.RISK,
                source_id=None,
                operation="raise",
                previous_value=object(),
                new_value=1,
            )


class TestDomainProfileConflict:
    def test_sources_must_not_be_empty(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileConflict(
                code="C1",
                field="required_rules",
                severity=DomainProfileConflictSeverity.ERROR,
                sources=(),
                description="conflict",
            )

    def test_roundtrip(self):
        c = DomainProfileConflict(
            code="C1",
            field="required_rules",
            severity=DomainProfileConflictSeverity.BLOCKING,
            sources=(DomainProfileSource.GLOBAL_POLICY, DomainProfileSource.RISK),
            description="mandatory vs prohibited",
            blocking=True,
        )
        assert DomainProfileConflict.from_dict(c.to_dict()) == c


class TestDomainProfileRejection:
    def test_roundtrip(self):
        r = DomainProfileRejection(
            source=DomainProfileSource.OPERATION,
            source_id="op-1",
            field="permissions",
            reason="irrelevant to primary domain",
        )
        assert DomainProfileRejection.from_dict(r.to_dict()) == r


class TestDomainProfileDecision:
    def test_roundtrip(self):
        d = DomainProfileDecision(
            code=DomainProfileDecisionCode.OVERLAY_APPLIED,
            field="reasoning_depth",
            source=DomainProfileSource.WORKFLOW,
        )
        assert DomainProfileDecision.from_dict(d.to_dict()) == d

    def test_invalid_code_rejected(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileDecision(
                code="not-a-code", field=None, source=DomainProfileSource.WORKFLOW
            )


# ── DomainProfileDraft ───────────────────────────────────────────────────────


class TestDomainProfileDraft:
    def test_draft_defaults_match_definition_defaults(self):
        d = DomainProfileDraft(primary_domain=DomainId("health"))
        assert d.minimum_confidence == 0.0
        assert d.reasoning_depth == DomainReasoningDepth.EXHAUSTIVE
        assert d.maximum_questions == 16
        assert d.modifications == ()

    def test_roundtrip(self):
        d = DomainProfileDraft(
            primary_domain=DomainId("health"),
            profile_names=("HealthProfile",),
            required_rules=("r1",),
            minimum_confidence=0.7,
        )
        assert DomainProfileDraft.from_dict(d.to_dict()) == d

    def test_has_no_id_trace_id_or_resolved_at_fields(self):
        d = DomainProfileDraft(primary_domain=DomainId("health"))
        assert not hasattr(d, "id")
        assert not hasattr(d, "trace_id")
        assert not hasattr(d, "resolved_at")


# ── ResolvedDomainProfile ───────────────────────────────────────────────────


class TestResolvedDomainProfile:
    def test_required_rules_cannot_overlap_prohibited(self):
        with pytest.raises(DomainProfileContractError):
            _resolved_profile(required_rules=("r1",), prohibited_rules=("r1",))

    def test_required_rules_cannot_overlap_optional(self):
        with pytest.raises(DomainProfileContractError):
            _resolved_profile(required_rules=("r1",), optional_rules=("r1",))

    def test_prohibited_inferences_must_not_remain_allowed(self):
        with pytest.raises(DomainProfileContractError):
            _resolved_profile(
                allowed_inferences=("i1", "i2"), prohibited_inferences=("i1",)
            )

    def test_prohibited_inferences_ok_when_allowed_is_unconstrained(self):
        rp = _resolved_profile(allowed_inferences=None, prohibited_inferences=("i1",))
        assert rp.prohibited_inferences == ("i1",)

    def test_priority_resources_must_remain_within_allowed(self):
        with pytest.raises(DomainProfileContractError):
            _resolved_profile(
                allowed_resource_kinds=("doc",), priority_resource_kinds=("note",)
            )

    def test_priority_resources_must_not_be_prohibited(self):
        with pytest.raises(DomainProfileContractError):
            _resolved_profile(
                priority_resource_kinds=("doc",), prohibited_resource_kinds=("doc",)
            )

    def test_minimum_confidence_bounds(self):
        with pytest.raises(DomainProfileContractError):
            _resolved_profile(minimum_confidence=-0.1)
        with pytest.raises(DomainProfileContractError):
            _resolved_profile(minimum_confidence=1.1)

    def test_maximum_questions_must_be_positive(self):
        with pytest.raises(DomainProfileContractError):
            _resolved_profile(maximum_questions=0)

    def test_resolved_at_must_be_tz_aware(self):
        naive_resolved_at = NOW.replace(tzinfo=None)
        with pytest.raises(DomainProfileContractError):
            _resolved_profile(resolved_at=naive_resolved_at)

    def test_roundtrip(self):
        rp = _resolved_profile()
        assert ResolvedDomainProfile.from_dict(rp.to_dict()) == rp


# ── DomainProfileCompositionResult ──────────────────────────────────────────


class TestDomainProfileCompositionResult:
    def test_profile_may_be_none(self):
        r = DomainProfileCompositionResult(profile=None)
        assert r.profile is None

    def test_profile_must_be_draft_type(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileCompositionResult(profile=_resolved_profile())

    def test_roundtrip(self):
        draft = DomainProfileDraft(primary_domain=DomainId("health"))
        conflict = DomainProfileConflict(
            code="C1",
            field="x",
            severity=DomainProfileConflictSeverity.WARNING,
            sources=(DomainProfileSource.RISK,),
            description="warn",
        )
        r = DomainProfileCompositionResult(profile=draft, conflicts=(conflict,))
        assert DomainProfileCompositionResult.from_dict(r.to_dict()) == r


# ── DomainProfileResolution status invariants ───────────────────────────────


class TestDomainProfileResolution:
    def test_resolved_requires_profile(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileResolution(
                id="res-1",
                status=DomainProfileResolutionStatus.RESOLVED,
                profile=None,
                trace_id="t",
                resolved_at=NOW,
            )

    def test_resolved_forbids_blocking_conflict(self):
        rp = _resolved_profile()
        blocking = DomainProfileConflict(
            code="C1",
            field="x",
            severity=DomainProfileConflictSeverity.BLOCKING,
            sources=(DomainProfileSource.RISK,),
            description="blocked",
            blocking=True,
        )
        with pytest.raises(DomainProfileContractError):
            DomainProfileResolution(
                id="res-1",
                status=DomainProfileResolutionStatus.RESOLVED,
                profile=rp,
                conflicts=(blocking,),
                trace_id="t",
                resolved_at=NOW,
            )

    def test_partial_requires_at_least_one_rejection(self):
        rp = _resolved_profile()
        with pytest.raises(DomainProfileContractError):
            DomainProfileResolution(
                id="res-1",
                status=DomainProfileResolutionStatus.PARTIAL,
                profile=rp,
                trace_id="t",
                resolved_at=NOW,
            )

    def test_partial_ok_with_rejection(self):
        rp = _resolved_profile()
        rejection = DomainProfileRejection(
            source=DomainProfileSource.OPERATION,
            source_id=None,
            field="permissions",
            reason="irrelevant",
        )
        res = DomainProfileResolution(
            id="res-1",
            status=DomainProfileResolutionStatus.PARTIAL,
            profile=rp,
            rejections=(rejection,),
            trace_id="t",
            resolved_at=NOW,
        )
        assert res.status == DomainProfileResolutionStatus.PARTIAL

    def test_blocked_forbids_profile(self):
        rp = _resolved_profile()
        with pytest.raises(DomainProfileContractError):
            DomainProfileResolution(
                id="res-1",
                status=DomainProfileResolutionStatus.BLOCKED,
                profile=rp,
                trace_id="t",
                resolved_at=NOW,
            )

    def test_blocked_requires_blocking_conflict(self):
        with pytest.raises(DomainProfileContractError):
            DomainProfileResolution(
                id="res-1",
                status=DomainProfileResolutionStatus.BLOCKED,
                profile=None,
                trace_id="t",
                resolved_at=NOW,
            )

    def test_blocked_ok_with_blocking_conflict(self):
        blocking = DomainProfileConflict(
            code="C1",
            field="x",
            severity=DomainProfileConflictSeverity.BLOCKING,
            sources=(DomainProfileSource.RISK,),
            description="blocked",
            blocking=True,
        )
        res = DomainProfileResolution(
            id="res-1",
            status=DomainProfileResolutionStatus.BLOCKED,
            profile=None,
            conflicts=(blocking,),
            trace_id="t",
            resolved_at=NOW,
        )
        assert res.status == DomainProfileResolutionStatus.BLOCKED

    def test_failed_forbids_profile(self):
        rp = _resolved_profile()
        with pytest.raises(DomainProfileContractError):
            DomainProfileResolution(
                id="res-1",
                status=DomainProfileResolutionStatus.FAILED,
                profile=rp,
                trace_id="t",
                resolved_at=NOW,
            )

    def test_failed_ok_without_profile(self):
        res = DomainProfileResolution(
            id="res-1",
            status=DomainProfileResolutionStatus.FAILED,
            profile=None,
            trace_id="t",
            resolved_at=NOW,
        )
        assert res.status == DomainProfileResolutionStatus.FAILED

    def test_roundtrip(self):
        rp = _resolved_profile()
        res = DomainProfileResolution(
            id="res-1",
            status=DomainProfileResolutionStatus.RESOLVED,
            profile=rp,
            trace_id="t",
            resolved_at=NOW,
        )
        assert DomainProfileResolution.from_dict(res.to_dict()) == res
