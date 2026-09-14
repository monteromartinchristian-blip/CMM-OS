"""Phase 10.11 – Dedicated serialization tests for Domain Profile contracts.

Covers every public Domain Profile contract: exact ``to_dict``/``from_dict``
round trips, unknown-field rejection, strict enum/bool/integer/float parsing,
bool-as-int rejection, non-finite float rejection, naive datetime rejection,
timezone-aware preservation, ``None`` vs empty tuple semantics, deeply frozen
metadata, JSON serialization, nested field paths in errors and no silent
coercion.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any

import pytest

from cmm.cognitive.enums import SensitivityLevel
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

_AWARE = datetime(2026, 8, 1, 12, 30, 0, tzinfo=timezone.utc)
_AWARE_OFFSET = datetime(
    2026, 8, 1, 12, 30, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))
)


# ── Builders: fully populated, invariant-safe instances ───────────────────────


def _question_policy() -> DomainQuestionPolicy:
    return DomainQuestionPolicy(
        maximum_questions=5,
        allow_follow_up=True,
        require_deduplication=True,
        allow_clarification=False,
        stop_on_blocking_gap=True,
        metadata={"policy": "question"},
    )


def _presentation_policy() -> DomainPresentationPolicy:
    return DomainPresentationPolicy(
        detail_level="detailed",
        include_uncertainty=True,
        include_provenance=False,
        include_alternatives=True,
        allow_speculation=False,
        require_disclaimers=True,
        metadata={"policy": "presentation"},
    )


def _memory_policy() -> DomainMemoryPolicy:
    return DomainMemoryPolicy(
        allow_read=True,
        allow_write=False,
        allow_long_term=True,
        allow_cross_domain=False,
        retention_scope="session",
        sensitivity_limit=SensitivityLevel.RESTRICTED,
        metadata={"policy": "memory"},
    )


def _temporal_policy() -> DomainTemporalPolicy:
    return DomainTemporalPolicy(
        require_current_information=True,
        allow_historical_information=False,
        maximum_age_seconds=3600,
        require_temporal_provenance=True,
        allow_future_projection=False,
        metadata={"policy": "temporal"},
    )


def _production_policy() -> DomainProductionPolicy:
    return DomainProductionPolicy(
        allow_draft=True,
        allow_final=False,
        allow_external_action=False,
        require_review=True,
        require_validation=True,
        maximum_output_items=25,
        metadata={"policy": "production"},
    )


def _definition() -> DomainProfileDefinition:
    return DomainProfileDefinition(
        id="profile-1",
        domain_id=DomainId("health"),
        profile_name="HealthProfile",
        required_rules=("rule.a", "rule.b"),
        optional_rules=("rule.c",),
        prohibited_rules=("rule.d",),
        allowed_resource_kinds=("document", "audio"),
        priority_resource_kinds=("document",),
        prohibited_resource_kinds=("video",),
        minimum_confidence=0.7,
        reasoning_depth=DomainReasoningDepth.DEEP,
        allowed_inferences=("infer.a",),
        prohibited_inferences=("infer.b",),
        maximum_questions=7,
        escalation_rules=("esc.a",),
        prohibited_actions=("act.a",),
        question_policy=_question_policy(),
        presentation_policy=_presentation_policy(),
        memory_policy=_memory_policy(),
        temporal_policy=_temporal_policy(),
        production_policy=_production_policy(),
        permissions=("perm.a", "perm.b"),
        metadata={"owner": "team"},
    )


def _overlay() -> DomainProfileOverlay:
    return DomainProfileOverlay(
        id="ov-1",
        source=DomainProfileSource.WORKFLOW,
        source_id="wf-1",
        priority=5,
        required_rules=("rule.x",),
        optional_rules=(),
        prohibited_rules=("rule.y",),
        allowed_resource_kinds=("document",),
        priority_resource_kinds=("document",),
        prohibited_resource_kinds=("audio",),
        minimum_confidence=0.9,
        reasoning_depth=DomainReasoningDepth.SHALLOW,
        allowed_inferences=("infer.z",),
        prohibited_inferences=("infer.w",),
        maximum_questions=3,
        escalation_rules=("esc.x",),
        prohibited_actions=("act.x",),
        question_policy=DomainQuestionPolicy(maximum_questions=2),
        presentation_policy=DomainPresentationPolicy(detail_level="minimal"),
        memory_policy=DomainMemoryPolicy(allow_write=False),
        temporal_policy=DomainTemporalPolicy(maximum_age_seconds=60),
        production_policy=DomainProductionPolicy(require_review=True),
        permissions=("perm.a",),
        reason="workflow requires narrowing",
        metadata={"origin": "test"},
    )


def _request() -> DomainProfileResolutionRequest:
    return DomainProfileResolutionRequest(
        id="req-1",
        primary_domain=DomainId("health"),
        supporting_domains=(DomainId("university"),),
        workflow_ids=("wf-1",),
        operation_ids=("op-1",),
        risk_level="high",
        actor_context={"role": "clinician"},
        autonomy_level="supervised",
        explicit_requirements=("req.a",),
        permissions=("perm.a",),
        metadata={"trace": "abc"},
    )


def _modification() -> DomainProfileModification:
    return DomainProfileModification(
        field="permissions",
        source=DomainProfileSource.EXPLICIT_REQUEST,
        source_id=None,
        operation="restrictive_intersection",
        previous_value=["perm.a", "perm.b"],
        new_value=["perm.a"],
        reason="request narrowed permissions",
        restrictive=True,
        metadata={"sequence": 3},
    )


def _conflict() -> DomainProfileConflict:
    return DomainProfileConflict(
        code="REQUIRED_AND_PROHIBITED_RULE",
        field="required_rules",
        severity=DomainProfileConflictSeverity.ERROR,
        sources=(DomainProfileSource.GLOBAL_POLICY, DomainProfileSource.PRIMARY_DOMAIN),
        description="rule.a is both required and prohibited",
        blocking=False,
        metadata={"rule": "rule.a"},
    )


def _blocking_conflict() -> DomainProfileConflict:
    return DomainProfileConflict(
        code="GLOBAL_MANDATORY_PROHIBITED",
        field="required_rules",
        severity=DomainProfileConflictSeverity.BLOCKING,
        sources=(DomainProfileSource.GLOBAL_POLICY,),
        description="global mandatory rule prohibited by overlay",
        blocking=True,
    )


def _rejection() -> DomainProfileRejection:
    return DomainProfileRejection(
        source=DomainProfileSource.WORKFLOW,
        source_id="wf-9",
        field="overlays",
        reason="overlay is not relevant to the request context",
        blocking=False,
        metadata={"overlay": "ov-9"},
    )


def _decision() -> DomainProfileDecision:
    return DomainProfileDecision(
        code=DomainProfileDecisionCode.OVERLAY_APPLIED,
        field="overlay",
        source=DomainProfileSource.RISK,
        source_id="high",
        reason="risk overlay matched",
        blocking=False,
        metadata={"note": "deterministic"},
    )


def _draft() -> DomainProfileDraft:
    return DomainProfileDraft(
        primary_domain=DomainId("health"),
        supporting_domains=(DomainId("university"),),
        profile_names=("GlobalProfile", "HealthProfile", "UniversityProfile"),
        required_rules=("rule.a",),
        optional_rules=("rule.c",),
        prohibited_rules=("rule.d",),
        allowed_resource_kinds=("document",),
        priority_resource_kinds=("document",),
        prohibited_resource_kinds=("video",),
        minimum_confidence=0.8,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=("infer.a",),
        prohibited_inferences=("infer.b",),
        maximum_questions=4,
        escalation_rules=("esc.a",),
        prohibited_actions=("act.a",),
        question_policy=_question_policy(),
        presentation_policy=_presentation_policy(),
        memory_policy=_memory_policy(),
        temporal_policy=_temporal_policy(),
        production_policy=_production_policy(),
        permissions=("perm.a",),
        modifications=(_modification(),),
        metadata={"stage": "draft"},
    )


def _resolved() -> ResolvedDomainProfile:
    return ResolvedDomainProfile(
        id="resolved-1",
        primary_domain=DomainId("health"),
        supporting_domains=(DomainId("university"),),
        profile_names=("GlobalProfile", "HealthProfile", "UniversityProfile"),
        required_rules=("rule.a",),
        optional_rules=("rule.c",),
        prohibited_rules=("rule.d",),
        allowed_resource_kinds=("document",),
        priority_resource_kinds=("document",),
        prohibited_resource_kinds=("video",),
        minimum_confidence=0.8,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=("infer.a",),
        prohibited_inferences=("infer.b",),
        maximum_questions=4,
        escalation_rules=("esc.a",),
        prohibited_actions=("act.a",),
        question_policy=_question_policy(),
        presentation_policy=_presentation_policy(),
        memory_policy=_memory_policy(),
        temporal_policy=_temporal_policy(),
        production_policy=_production_policy(),
        permissions=("perm.a",),
        modifications=(_modification(),),
        trace_id="trace-1",
        resolved_at=_AWARE,
        metadata={"stage": "resolved"},
    )


def _composition_result() -> DomainProfileCompositionResult:
    return DomainProfileCompositionResult(
        profile=_draft(),
        conflicts=(_conflict(),),
        rejections=(_rejection(),),
        decisions=(_decision(),),
        modifications=(_modification(),),
        metadata={"pure": True},
    )


def _resolution_resolved() -> DomainProfileResolution:
    return DomainProfileResolution(
        id="resolution-1",
        status=DomainProfileResolutionStatus.RESOLVED,
        profile=_resolved(),
        conflicts=(),
        rejections=(),
        decisions=(_decision(),),
        trace_id="trace-1",
        resolved_at=_AWARE,
        metadata={"final": True},
    )


def _resolution_partial() -> DomainProfileResolution:
    return DomainProfileResolution(
        id="resolution-2",
        status=DomainProfileResolutionStatus.PARTIAL,
        profile=_resolved(),
        conflicts=(),
        rejections=(_rejection(),),
        decisions=(_decision(),),
        trace_id="trace-2",
        resolved_at=_AWARE,
    )


def _resolution_blocked() -> DomainProfileResolution:
    return DomainProfileResolution(
        id="resolution-3",
        status=DomainProfileResolutionStatus.BLOCKED,
        profile=None,
        conflicts=(_blocking_conflict(),),
        rejections=(),
        decisions=(),
        trace_id="trace-3",
        resolved_at=_AWARE,
    )


_ROUND_TRIP_CASES = [
    (DomainQuestionPolicy, _question_policy()),
    (DomainPresentationPolicy, _presentation_policy()),
    (DomainMemoryPolicy, _memory_policy()),
    (DomainTemporalPolicy, _temporal_policy()),
    (DomainProductionPolicy, _production_policy()),
    (DomainProfileDefinition, _definition()),
    (DomainProfileOverlay, _overlay()),
    (DomainProfileResolutionRequest, _request()),
    (DomainProfileModification, _modification()),
    (DomainProfileConflict, _conflict()),
    (DomainProfileRejection, _rejection()),
    (DomainProfileDecision, _decision()),
    (DomainProfileDraft, _draft()),
    (ResolvedDomainProfile, _resolved()),
    (DomainProfileCompositionResult, _composition_result()),
    (DomainProfileResolution, _resolution_resolved()),
    (DomainProfileResolution, _resolution_partial()),
    (DomainProfileResolution, _resolution_blocked()),
]


# ── Exact round trips ──────────────────────────────────────────────────────────


class TestExactRoundTrips:
    @pytest.mark.parametrize(("contract_cls", "instance"), _ROUND_TRIP_CASES)
    def test_exact_to_dict_from_dict_round_trip(self, contract_cls, instance) -> None:
        data = instance.to_dict()
        restored = contract_cls.from_dict(data)
        assert restored == instance
        assert restored.to_dict() == data

    @pytest.mark.parametrize(("contract_cls", "instance"), _ROUND_TRIP_CASES)
    def test_to_dict_produces_plain_containers(self, contract_cls, instance) -> None:
        def assert_plain(value: Any) -> None:
            assert not isinstance(value, MappingProxyType)
            if isinstance(value, dict):
                assert type(value) is dict
                for key, item in value.items():
                    assert type(key) is str
                    assert_plain(item)
            elif isinstance(value, (list, tuple)):
                assert type(value) is list
                for item in value:
                    assert_plain(item)

        assert_plain(instance.to_dict())


# ── JSON serialization ─────────────────────────────────────────────────────────


class TestJsonSerialization:
    @pytest.mark.parametrize(("contract_cls", "instance"), _ROUND_TRIP_CASES)
    def test_json_round_trip(self, contract_cls, instance) -> None:
        payload = json.dumps(instance.to_dict())
        restored = contract_cls.from_dict(json.loads(payload))
        assert restored == instance
        assert json.dumps(restored.to_dict()) == payload


# ── Unknown fields rejected ────────────────────────────────────────────────────


class TestUnknownFieldsRejected:
    @pytest.mark.parametrize(("contract_cls", "instance"), _ROUND_TRIP_CASES)
    def test_unknown_field_rejected(self, contract_cls, instance) -> None:
        data = instance.to_dict()
        data["unknown_extra_field"] = "surprise"
        with pytest.raises(DomainProfileSerializationError) as exc_info:
            contract_cls.from_dict(data)
        assert exc_info.value.field == "data"
        assert "unknown_extra_field" in exc_info.value.details["unknown_fields"]

    @pytest.mark.parametrize(("contract_cls", "instance"), _ROUND_TRIP_CASES)
    def test_non_mapping_rejected(self, contract_cls, instance) -> None:
        with pytest.raises(DomainProfileSerializationError):
            contract_cls.from_dict(["not", "a", "mapping"])


# ── Missing required fields ────────────────────────────────────────────────────


class TestMissingRequiredFields:
    def test_definition_missing_domain_id(self) -> None:
        data = _definition().to_dict()
        del data["domain_id"]
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileDefinition.from_dict(data)

    def test_overlay_missing_source(self) -> None:
        data = _overlay().to_dict()
        del data["source"]
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileOverlay.from_dict(data)

    def test_request_missing_primary_domain(self) -> None:
        data = _request().to_dict()
        del data["primary_domain"]
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileResolutionRequest.from_dict(data)

    def test_modification_missing_new_value(self) -> None:
        data = _modification().to_dict()
        del data["new_value"]
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileModification.from_dict(data)

    def test_conflict_missing_sources(self) -> None:
        data = _conflict().to_dict()
        del data["sources"]
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileConflict.from_dict(data)

    def test_resolution_missing_trace_id(self) -> None:
        data = _resolution_resolved().to_dict()
        del data["trace_id"]
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileResolution.from_dict(data)

    def test_resolved_missing_resolved_at(self) -> None:
        data = _resolved().to_dict()
        del data["resolved_at"]
        with pytest.raises(DomainProfileSerializationError):
            ResolvedDomainProfile.from_dict(data)


# ── Strict enum parsing ────────────────────────────────────────────────────────


class TestStrictEnumParsing:
    def test_overlay_invalid_source_string_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(id="ov", source="not_a_source")

    def test_overlay_non_string_source_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(id="ov", source=1)

    def test_overlay_from_dict_invalid_source_rejected(self) -> None:
        data = _overlay().to_dict()
        data["source"] = "upstream"
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileOverlay.from_dict(data)

    def test_definition_invalid_reasoning_depth_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                reasoning_depth="bottomless",
            )

    def test_definition_reasoning_depth_bool_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                reasoning_depth=True,
            )

    def test_conflict_invalid_severity_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileConflict(
                code="C",
                field="f",
                severity="catastrophic",
                sources=(DomainProfileSource.RISK,),
                description="d",
            )

    def test_decision_invalid_code_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDecision(
                code="not_a_code",
                field="f",
                source=DomainProfileSource.ACTOR,
            )

    def test_resolution_invalid_status_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileResolution(
                id="r",
                status="half_done",
                profile=None,
                trace_id="t",
                resolved_at=_AWARE,
            )

    def test_memory_policy_invalid_sensitivity_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainMemoryPolicy(sensitivity_limit="ultra")

    def test_memory_policy_from_dict_invalid_sensitivity_rejected(self) -> None:
        data = _memory_policy().to_dict()
        data["sensitivity_limit"] = "ultra"
        with pytest.raises(DomainProfileSerializationError):
            DomainMemoryPolicy.from_dict(data)

    def test_valid_enum_strings_accepted(self) -> None:
        overlay = DomainProfileOverlay(id="ov", source="risk", source_id="high")
        assert overlay.source is DomainProfileSource.RISK
        policy = DomainMemoryPolicy(sensitivity_limit="restricted")
        assert policy.sensitivity_limit is SensitivityLevel.RESTRICTED
        definition = DomainProfileDefinition(
            id="p",
            domain_id=DomainId("health"),
            profile_name="P",
            reasoning_depth="exhaustive",
        )
        assert definition.reasoning_depth is DomainReasoningDepth.EXHAUSTIVE


class TestOverlaySourceIdSerialization:
    def _assert_missing_source_id_rejected(self, source: DomainProfileSource) -> None:
        with pytest.raises(DomainProfileSerializationError, match="source_id"):
            DomainProfileOverlay.from_dict({"id": "ov", "source": source.value})

    def test_primary_overlay_requires_source_id(self) -> None:
        self._assert_missing_source_id_rejected(DomainProfileSource.PRIMARY_DOMAIN)

    def test_supporting_overlay_requires_source_id(self) -> None:
        self._assert_missing_source_id_rejected(DomainProfileSource.SUPPORTING_DOMAIN)

    def test_workflow_overlay_requires_source_id(self) -> None:
        self._assert_missing_source_id_rejected(DomainProfileSource.WORKFLOW)

    def test_operation_overlay_requires_source_id(self) -> None:
        self._assert_missing_source_id_rejected(DomainProfileSource.OPERATION)

    def test_risk_overlay_requires_source_id(self) -> None:
        self._assert_missing_source_id_rejected(DomainProfileSource.RISK)

    def test_actor_overlay_requires_source_id(self) -> None:
        self._assert_missing_source_id_rejected(DomainProfileSource.ACTOR)

    def test_autonomy_overlay_requires_source_id(self) -> None:
        self._assert_missing_source_id_rejected(DomainProfileSource.AUTONOMY)

    def test_explicit_request_overlay_requires_source_id(self) -> None:
        self._assert_missing_source_id_rejected(DomainProfileSource.EXPLICIT_REQUEST)

    def test_global_overlay_may_omit_source_id(self) -> None:
        overlay = DomainProfileOverlay.from_dict(
            {"id": "ov", "source": DomainProfileSource.GLOBAL_POLICY.value}
        )
        assert overlay.source_id is None


def test_definition_approved_defaults_round_trip() -> None:
    definition = DomainProfileDefinition.from_dict(
        {"id": "p", "domain_id": "domain:health", "profile_name": "HealthProfile"}
    )
    assert definition.reasoning_depth is DomainReasoningDepth.EXHAUSTIVE
    assert definition.maximum_questions == 16
    assert definition.to_dict()["reasoning_depth"] == "exhaustive"
    assert definition.to_dict()["maximum_questions"] == 16


def test_invalid_permanent_retention_rejected() -> None:
    with pytest.raises(DomainProfileSerializationError):
        DomainMemoryPolicy.from_dict({"retention_scope": "permanent"})


# ── Strict bool parsing ────────────────────────────────────────────────────────


class TestStrictBoolParsing:
    @pytest.mark.parametrize("bad", [1, 0, "true", "false", 1.0, []])
    def test_policy_bool_fields_reject_non_bool(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainQuestionPolicy(allow_follow_up=bad)
        with pytest.raises(DomainProfileContractError):
            DomainPresentationPolicy(include_uncertainty=bad)
        with pytest.raises(DomainProfileContractError):
            DomainMemoryPolicy(allow_read=bad)
        with pytest.raises(DomainProfileContractError):
            DomainTemporalPolicy(require_current_information=bad)
        with pytest.raises(DomainProfileContractError):
            DomainProductionPolicy(allow_draft=bad)

    def test_policy_from_dict_rejects_non_bool(self) -> None:
        data = _question_policy().to_dict()
        data["allow_follow_up"] = 1
        with pytest.raises(DomainProfileSerializationError):
            DomainQuestionPolicy.from_dict(data)

    def test_modification_restrictive_rejects_int(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileModification(
                field="f",
                source=DomainProfileSource.RISK,
                source_id=None,
                operation="op",
                previous_value=None,
                new_value=1,
                restrictive=1,
            )

    def test_conflict_blocking_rejects_int(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileConflict(
                code="C",
                field="f",
                severity=DomainProfileConflictSeverity.WARNING,
                sources=(DomainProfileSource.RISK,),
                description="d",
                blocking=0,
            )

    def test_rejection_blocking_rejects_string(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileRejection(
                source=DomainProfileSource.WORKFLOW,
                source_id="wf",
                field="overlays",
                reason="r",
                blocking="no",
            )

    def test_decision_blocking_rejects_int(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDecision(
                code=DomainProfileDecisionCode.PROFILE_APPLIED,
                field="profile",
                source=DomainProfileSource.GLOBAL_POLICY,
                blocking=1,
            )

    def test_bool_fields_round_trip_preserves_true_and_false(self) -> None:
        policy = DomainQuestionPolicy(allow_follow_up=True, allow_clarification=False)
        restored = DomainQuestionPolicy.from_dict(policy.to_dict())
        assert restored.allow_follow_up is True
        assert restored.allow_clarification is False


# ── Bool-as-int rejected ───────────────────────────────────────────────────────


class TestBoolAsIntRejected:
    @pytest.mark.parametrize("bad", [True, False])
    def test_maximum_questions_rejects_bool(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainQuestionPolicy(maximum_questions=bad)

    @pytest.mark.parametrize("bad", [True, False])
    def test_definition_maximum_questions_rejects_bool(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                maximum_questions=bad,
            )

    @pytest.mark.parametrize("bad", [True, False])
    def test_overlay_maximum_questions_rejects_bool(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(
                id="ov",
                source=DomainProfileSource.RISK,
                source_id="high",
                maximum_questions=bad,
            )

    @pytest.mark.parametrize("bad", [True, False])
    def test_overlay_priority_rejects_bool(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(
                id="ov",
                source=DomainProfileSource.RISK,
                source_id="high",
                priority=bad,
            )

    @pytest.mark.parametrize("bad", [True, False])
    def test_maximum_age_seconds_rejects_bool(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainTemporalPolicy(maximum_age_seconds=bad)

    @pytest.mark.parametrize("bad", [True, False])
    def test_maximum_output_items_rejects_bool(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProductionPolicy(maximum_output_items=bad)

    def test_from_dict_bool_as_int_rejected(self) -> None:
        data = _overlay().to_dict()
        data["priority"] = True
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileOverlay.from_dict(data)

    def test_plain_int_still_accepted(self) -> None:
        policy = DomainQuestionPolicy(maximum_questions=1)
        assert policy.maximum_questions == 1
        overlay = DomainProfileOverlay(
            id="ov", source=DomainProfileSource.RISK, source_id="high", priority=0
        )
        assert overlay.priority == 0


# ── Strict integer parsing ─────────────────────────────────────────────────────


class TestStrictIntegerParsing:
    @pytest.mark.parametrize("bad", ["5", 5.0, 5.5, [5], (5,)])
    def test_maximum_questions_rejects_non_int(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainQuestionPolicy(maximum_questions=bad)

    @pytest.mark.parametrize("bad", ["3", 3.5, [3]])
    def test_overlay_priority_rejects_non_int(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(
                id="ov",
                source=DomainProfileSource.RISK,
                source_id="high",
                priority=bad,
            )

    @pytest.mark.parametrize("bad", ["60", 60.5, [60]])
    def test_maximum_age_seconds_rejects_non_int(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainTemporalPolicy(maximum_age_seconds=bad)

    def test_maximum_questions_zero_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainQuestionPolicy(maximum_questions=0)

    def test_maximum_questions_negative_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainQuestionPolicy(maximum_questions=-3)

    def test_maximum_age_seconds_negative_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainTemporalPolicy(maximum_age_seconds=-1)

    def test_maximum_age_seconds_zero_allowed(self) -> None:
        policy = DomainTemporalPolicy(maximum_age_seconds=0)
        assert policy.maximum_age_seconds == 0

    def test_from_dict_strict_int(self) -> None:
        data = _question_policy().to_dict()
        data["maximum_questions"] = "5"
        with pytest.raises(DomainProfileSerializationError):
            DomainQuestionPolicy.from_dict(data)


# ── Strict float parsing ───────────────────────────────────────────────────────


class TestStrictFloatParsing:
    @pytest.mark.parametrize("bad", ["0.5", True, False, [0.5], (0.5,)])
    def test_minimum_confidence_rejects_non_numeric(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                minimum_confidence=bad,
            )

    @pytest.mark.parametrize("bad", ["0.5", True, [0.5]])
    def test_overlay_minimum_confidence_rejects_non_numeric(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(
                id="ov",
                source=DomainProfileSource.RISK,
                source_id="high",
                minimum_confidence=bad,
            )

    def test_minimum_confidence_out_of_range_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                minimum_confidence=1.5,
            )
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                minimum_confidence=-0.1,
            )

    def test_minimum_confidence_from_dict_strict(self) -> None:
        data = _definition().to_dict()
        data["minimum_confidence"] = "0.7"
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileDefinition.from_dict(data)

    def test_int_accepted_as_confidence_and_stored_as_float(self) -> None:
        definition = DomainProfileDefinition(
            id="p",
            domain_id=DomainId("health"),
            profile_name="P",
            minimum_confidence=1,
        )
        assert definition.minimum_confidence == 1.0
        assert isinstance(definition.minimum_confidence, float)


# ── NaN / inf rejected ─────────────────────────────────────────────────────────


class TestNonFiniteRejected:
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_minimum_confidence_non_finite_rejected(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                minimum_confidence=bad,
            )

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_overlay_minimum_confidence_non_finite_rejected(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(
                id="ov",
                source=DomainProfileSource.RISK,
                source_id="high",
                minimum_confidence=bad,
            )

    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_metadata_non_finite_float_rejected(self, bad) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainQuestionPolicy(metadata={"value": bad})

    def test_overlay_from_dict_non_finite_confidence_rejected(self) -> None:
        data = _overlay().to_dict()
        data["minimum_confidence"] = float("nan")
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileOverlay.from_dict(data)


# ── Datetimes ──────────────────────────────────────────────────────────────────


class TestDatetimes:
    def test_naive_datetime_rejected_on_construction(self) -> None:
        with pytest.raises(DomainProfileContractError):
            ResolvedDomainProfile(
                id="r",
                primary_domain=DomainId("health"),
                supporting_domains=(),
                profile_names=(),
                required_rules=(),
                optional_rules=(),
                prohibited_rules=(),
                allowed_resource_kinds=None,
                priority_resource_kinds=(),
                prohibited_resource_kinds=(),
                minimum_confidence=0.0,
                reasoning_depth=DomainReasoningDepth.STANDARD,
                allowed_inferences=None,
                prohibited_inferences=(),
                maximum_questions=10,
                escalation_rules=(),
                prohibited_actions=(),
                question_policy=DomainQuestionPolicy(),
                presentation_policy=DomainPresentationPolicy(),
                memory_policy=DomainMemoryPolicy(),
                temporal_policy=DomainTemporalPolicy(),
                production_policy=DomainProductionPolicy(),
                permissions=None,
                modifications=(),
                trace_id="t",
                resolved_at=datetime.fromisoformat("2026-08-01T12:00:00"),
            )

    def test_naive_iso_string_rejected_from_dict(self) -> None:
        data = _resolved().to_dict()
        data["resolved_at"] = "2026-08-01T12:30:00"
        with pytest.raises(DomainProfileSerializationError):
            ResolvedDomainProfile.from_dict(data)

    def test_naive_datetime_object_rejected_from_dict(self) -> None:
        data = _resolution_resolved().to_dict()
        data["resolved_at"] = datetime.fromisoformat("2026-08-01T12:30:00")
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileResolution.from_dict(data)

    def test_resolution_naive_iso_string_rejected_from_dict(self) -> None:
        data = _resolution_resolved().to_dict()
        data["resolved_at"] = "2026-08-01T12:30:00"
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileResolution.from_dict(data)

    def test_invalid_datetime_string_rejected(self) -> None:
        data = _resolved().to_dict()
        data["resolved_at"] = "not-a-datetime"
        with pytest.raises(DomainProfileSerializationError):
            ResolvedDomainProfile.from_dict(data)

    def test_null_resolved_at_rejected(self) -> None:
        data = _resolved().to_dict()
        data["resolved_at"] = None
        with pytest.raises(DomainProfileSerializationError):
            ResolvedDomainProfile.from_dict(data)

    def test_timezone_aware_datetime_preserved(self) -> None:
        resolved = ResolvedDomainProfile.from_dict(
            {**_resolved().to_dict(), "resolved_at": _AWARE_OFFSET.isoformat()}
        )
        assert resolved.resolved_at == _AWARE_OFFSET
        assert resolved.resolved_at.utcoffset() == timedelta(hours=5, minutes=30)

    def test_timezone_offset_preserved_through_json(self) -> None:
        data = _resolved().to_dict()
        data["resolved_at"] = _AWARE_OFFSET.isoformat()
        restored = ResolvedDomainProfile.from_dict(json.loads(json.dumps(data)))
        assert restored.resolved_at == _AWARE_OFFSET
        assert restored.resolved_at.utcoffset() == timedelta(hours=5, minutes=30)


# ── None vs empty tuple ────────────────────────────────────────────────────────


class TestNoneVsEmptyTuple:
    def test_definition_none_means_unconstrained_empty_means_none_allowed(self) -> None:
        none_def = DomainProfileDefinition(
            id="p1",
            domain_id=DomainId("health"),
            profile_name="P1",
            allowed_resource_kinds=None,
            permissions=None,
            allowed_inferences=None,
        )
        empty_def = DomainProfileDefinition(
            id="p2",
            domain_id=DomainId("university"),
            profile_name="P2",
            allowed_resource_kinds=(),
            permissions=(),
            allowed_inferences=(),
        )
        assert none_def.to_dict()["allowed_resource_kinds"] is None
        assert none_def.to_dict()["permissions"] is None
        assert none_def.to_dict()["allowed_inferences"] is None
        assert empty_def.to_dict()["allowed_resource_kinds"] == []
        assert empty_def.to_dict()["permissions"] == []
        assert empty_def.to_dict()["allowed_inferences"] == []

        none_restored = DomainProfileDefinition.from_dict(none_def.to_dict())
        empty_restored = DomainProfileDefinition.from_dict(empty_def.to_dict())
        assert none_restored.allowed_resource_kinds is None
        assert none_restored.permissions is None
        assert none_restored.allowed_inferences is None
        assert empty_restored.allowed_resource_kinds == ()
        assert empty_restored.permissions == ()
        assert empty_restored.allowed_inferences == ()

    def test_overlay_none_vs_empty_preserved(self) -> None:
        none_overlay = DomainProfileOverlay(
            id="ov-none",
            source=DomainProfileSource.RISK,
            source_id="high",
            required_rules=None,
        )
        empty_overlay = DomainProfileOverlay(
            id="ov-empty",
            source=DomainProfileSource.RISK,
            source_id="high",
            required_rules=(),
        )
        assert none_overlay.to_dict()["required_rules"] is None
        assert empty_overlay.to_dict()["required_rules"] == []
        assert (
            DomainProfileOverlay.from_dict(none_overlay.to_dict()).required_rules
            is None
        )
        assert (
            DomainProfileOverlay.from_dict(empty_overlay.to_dict()).required_rules == ()
        )

    def test_request_permissions_none_vs_empty_preserved(self) -> None:
        none_request = DomainProfileResolutionRequest(
            id="r1", primary_domain=DomainId("health"), permissions=None
        )
        empty_request = DomainProfileResolutionRequest(
            id="r2", primary_domain=DomainId("health"), permissions=()
        )
        assert none_request.to_dict()["permissions"] is None
        assert empty_request.to_dict()["permissions"] == []
        assert (
            DomainProfileResolutionRequest.from_dict(none_request.to_dict()).permissions
            is None
        )
        assert (
            DomainProfileResolutionRequest.from_dict(
                empty_request.to_dict()
            ).permissions
            == ()
        )

    def test_draft_allowed_inferences_none_vs_empty_preserved(self) -> None:
        draft_none = DomainProfileDraft(
            primary_domain=DomainId("health"), allowed_inferences=None
        )
        draft_empty = DomainProfileDraft(
            primary_domain=DomainId("health"), allowed_inferences=()
        )
        assert (
            DomainProfileDraft.from_dict(draft_none.to_dict()).allowed_inferences
            is None
        )
        assert (
            DomainProfileDraft.from_dict(draft_empty.to_dict()).allowed_inferences == ()
        )


# ── Nested metadata deep freeze ────────────────────────────────────────────────


class TestNestedMetadataDeepFreeze:
    def test_metadata_is_deeply_frozen(self) -> None:
        policy = DomainQuestionPolicy(
            metadata={"outer": {"items": [1, {"deep": True}]}}
        )
        assert isinstance(policy.metadata, MappingProxyType)
        assert isinstance(policy.metadata["outer"], MappingProxyType)
        assert isinstance(policy.metadata["outer"]["items"], tuple)
        assert isinstance(policy.metadata["outer"]["items"][1], MappingProxyType)
        with pytest.raises(TypeError):
            policy.metadata["outer"]["x"] = 1
        with pytest.raises(TypeError):
            policy.metadata["new"] = 1

    def test_to_dict_unfreezes_metadata(self) -> None:
        policy = DomainQuestionPolicy(
            metadata={"outer": {"items": [1, {"deep": True}]}}
        )
        metadata = policy.to_dict()["metadata"]
        assert metadata == {"outer": {"items": [1, {"deep": True}]}}
        assert type(metadata) is dict
        assert type(metadata["outer"]) is dict
        assert type(metadata["outer"]["items"]) is list
        assert type(metadata["outer"]["items"][1]) is dict

    def test_source_mapping_mutation_does_not_leak(self) -> None:
        source = {"nested": {"values": [1, 2]}}
        policy = DomainQuestionPolicy(metadata=source)
        source["nested"]["values"].append(3)
        assert policy.metadata["nested"]["values"] == (1, 2)

    def test_definition_metadata_deep_frozen(self) -> None:
        definition = DomainProfileDefinition(
            id="p",
            domain_id=DomainId("health"),
            profile_name="P",
            metadata={"a": {"b": [{"c": 1}]}},
        )
        assert isinstance(definition.metadata["a"], MappingProxyType)
        assert isinstance(definition.metadata["a"]["b"], tuple)
        assert isinstance(definition.metadata["a"]["b"][0], MappingProxyType)

    def test_metadata_non_json_safe_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainQuestionPolicy(metadata={"bad": object()})

    def test_metadata_non_string_keys_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainQuestionPolicy(metadata={1: "one"})


# ── Nested field paths in errors ───────────────────────────────────────────────


class TestNestedFieldPaths:
    def test_supporting_domains_index_path(self) -> None:
        data = _request().to_dict()
        data["supporting_domains"] = ["domain:Invalid Slug!!"]
        with pytest.raises(DomainProfileSerializationError) as exc_info:
            DomainProfileResolutionRequest.from_dict(data)
        assert exc_info.value.field == "supporting_domains[0]"

    def test_supporting_domains_non_canonical_rejected(self) -> None:
        data = _request().to_dict()
        data["supporting_domains"] = ["not-canonical"]
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileResolutionRequest.from_dict(data)

    def test_conflict_sources_index_path(self) -> None:
        data = _conflict().to_dict()
        data["sources"] = ["global_policy", "bogus"]
        with pytest.raises(DomainProfileSerializationError) as exc_info:
            DomainProfileConflict.from_dict(data)
        assert exc_info.value.field == "sources[1]"

    def test_metadata_nested_path(self) -> None:
        data = _question_policy().to_dict()
        data["metadata"] = {"outer": {"inner": float("nan")}}
        with pytest.raises(DomainProfileSerializationError) as exc_info:
            DomainQuestionPolicy.from_dict(data)
        assert exc_info.value.field == "metadata.outer.inner"

    def test_definition_metadata_nested_path(self) -> None:
        with pytest.raises(DomainProfileContractError) as exc_info:
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                metadata={"a": {"b": object()}},
            )
        assert exc_info.value.field == "metadata.a.b"

    def test_unknown_field_error_lists_field_names(self) -> None:
        data = _question_policy().to_dict()
        data["mystery"] = 1
        with pytest.raises(DomainProfileSerializationError) as exc_info:
            DomainQuestionPolicy.from_dict(data)
        assert "mystery" in exc_info.value.message


# ── No silent coercion ─────────────────────────────────────────────────────────


class TestNoSilentCoercion:
    def test_definition_id_rejects_non_string(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id=123, domain_id=DomainId("health"), profile_name="P"
            )

    def test_definition_from_dict_id_rejects_non_string(self) -> None:
        data = _definition().to_dict()
        data["id"] = 123
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileDefinition.from_dict(data)

    def test_domain_id_rejects_non_canonical_string(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(id="p", domain_id="health", profile_name="P")

    def test_domain_id_rejects_int(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(id="p", domain_id=7, profile_name="P")

    def test_required_rules_rejects_plain_string(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                required_rules="rule.a",
            )

    def test_workflow_ids_rejects_plain_string(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileResolutionRequest(
                id="r", primary_domain=DomainId("health"), workflow_ids="wf-1"
            )

    def test_permissions_rejects_plain_string(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                permissions="perm.a",
            )

    def test_detail_level_rejects_unknown_value(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainPresentationPolicy(detail_level="verbose")

    def test_retention_scope_rejects_unknown_value(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainMemoryPolicy(retention_scope="forever-ish")

    def test_duplicate_items_rejected(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                required_rules=("rule.a", "rule.a"),
            )

    def test_enum_not_coerced_from_int(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileOverlay(id="ov", source=0)

    def test_nested_policy_mapping_coerced_explicitly(self) -> None:
        definition = DomainProfileDefinition(
            id="p",
            domain_id=DomainId("health"),
            profile_name="P",
            question_policy={"maximum_questions": 3},
        )
        assert isinstance(definition.question_policy, DomainQuestionPolicy)
        assert definition.question_policy.maximum_questions == 3

    def test_nested_policy_rejects_invalid_mapping(self) -> None:
        # A nested policy supplied as a raw mapping is parsed through
        # ``from_dict``, so invalid content surfaces as a serialization error.
        with pytest.raises(DomainProfileSerializationError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                question_policy={"maximum_questions": "3"},
            )

    def test_nested_policy_rejects_non_mapping(self) -> None:
        with pytest.raises(DomainProfileContractError):
            DomainProfileDefinition(
                id="p",
                domain_id=DomainId("health"),
                profile_name="P",
                question_policy="policy",
            )
