"""Phase 10.41 — strict immutable integration contract tests (Task 2)."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
from types import MappingProxyType

import pytest

from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
)
from cmm.domains.agent_runtime_integration_contracts import (
    DomainActionBudget,
    DomainAgentRuntimeDecision,
    DomainAgentRuntimeDecisionCode,
    DomainAgentRuntimeIntegrationRequest,
    DomainAgentRuntimeIntegrationResult,
)
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.errors import DomainAgentRuntimeIntegrationContractError
from cmm.domains.identifiers import DomainId
from cmm.domains.profile_contracts import (
    DomainProfileDefinition,
    DomainProfileResolutionRequest,
)
from cmm.domains.profile_resolver import DefaultDomainProfileResolver
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.university.definition import build_university_domain_definition

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)

# Neutral placeholder used as the VALUE of metadata keys that contracts must
# reject because the KEY is secret-bearing or hidden-reasoning shaped.
TEST_METADATA_VALUE = "test-value-1041"

ALL_DECISION_CODES = (
    "DOMAIN_RESOLVED",
    "DOMAIN_REEVALUATED",
    "PRIMARY_DOMAIN_CHANGED",
    "SUPPORTING_DOMAIN_ADDED",
    "DOMAIN_COMPOSED",
    "PROFILE_RESOLVED",
    "DOMAIN_PERMISSION_RESTRICTED",
    "DOMAIN_APPROVAL_REQUIRED",
    "DOMAIN_AUTONOMY_RESTRICTED",
    "DOMAIN_BUDGET_RESTRICTED",
    "DOMAIN_OPERATION_SELECTED",
    "DOMAIN_WORKFLOW_BOUND",
    "DOMAIN_COGNITIVE_BOUND",
    "DOMAIN_RUNTIME_BLOCKED",
    "DOMAIN_RUNTIME_COMPLETED",
)

HIDDEN_REASONING_KEYS = (
    "chain_of_thought",
    "reasoning_text",
    "internal_reasoning",
    "scratchpad",
    "hidden_trace",
)


# ── Canonical object fixtures ─────────────────────────────────────────────────


def _resolution_context(**overrides: object) -> DomainResolutionContext:
    values: dict[str, object] = {
        "id": "res-ctx-1041",
        "user_input": "University examination in Room 101",
        "available_domains": (DomainId("university"),),
        "authorized_domains": (DomainId("university"),),
        "explicit_domains": (DomainId("university"),),
        "active_domains": (),
        "created_at": NOW,
    }
    values.update(overrides)
    return DomainResolutionContext(**values)


def _resolution() -> object:
    resolver = DefaultDomainResolver(
        fallback_domain=DomainId("general"),
        clock=lambda: NOW,
        id_factory=lambda: "res-result-1041",
    )
    return resolver.resolve(_resolution_context())


def _composition() -> object:
    composer = DefaultDomainComposer(
        id_factory=lambda: "composition-1041", clock=lambda: NOW
    )
    return composer.compose(_resolution(), (build_university_domain_definition(),))


def _profile() -> object:
    resolver = DefaultDomainProfileResolver(
        clock=lambda: NOW,
        id_factory=lambda: "prof-res-1041",
        profile_id_factory=lambda: "resolved-profile-1041",
        trace_id_factory=lambda: "prof-trace-1041",
    )
    return resolver.resolve(
        request=DomainProfileResolutionRequest(
            id="prof-req-1041",
            primary_domain=DomainId("university"),
            supporting_domains=(),
        ),
        global_profile=DomainProfileDefinition(
            id="general.profile",
            domain_id=DomainId("general"),
            profile_name="GeneralProfile",
        ),
        primary_profile=DomainProfileDefinition(
            id="university.profile",
            domain_id=DomainId("university"),
            profile_name="UniversityProfile",
            required_rules=("university.deadline",),
            minimum_confidence=0.75,
            reasoning_depth=DomainReasoningDepth.STANDARD,
            maximum_questions=10,
        ),
        supporting_profiles=(),
        overlays=(),
    ).profile


def _agent_request(**overrides: object) -> IntegratedAgentExecutionRequest:
    values: dict[str, object] = {
        "execution_id": "exec-1041",
        "request_id": "req-1041",
        "goal_id": "goal-1041",
        "actor_id": "actor-1041",
        "owner_actor_id": "actor-1041",
        "max_autonomy_level": 2,
        "created_at": NOW,
    }
    values.update(overrides)
    return IntegratedAgentExecutionRequest(**values)


def _budget(**overrides: object) -> DomainActionBudget:
    return DomainActionBudget(domain_id="domain:university", **overrides)


def _decision(**overrides: object) -> DomainAgentRuntimeDecision:
    values: dict[str, object] = {
        "code": DomainAgentRuntimeDecisionCode.DOMAIN_RESOLVED,
        "subject_id": "res-result-1041",
        "reason_codes": ("explicit_domain_selected",),
        "related_ids": ("res-ctx-1041",),
    }
    values.update(overrides)
    return DomainAgentRuntimeDecision(**values)


def _integration_request(**overrides: object) -> DomainAgentRuntimeIntegrationRequest:
    values: dict[str, object] = {
        "request_id": "int-req-1041",
        "resolution_context": _resolution_context(),
        "agent_request": _agent_request(),
    }
    values.update(overrides)
    return DomainAgentRuntimeIntegrationRequest(**values)


def _integration_result(**overrides: object) -> DomainAgentRuntimeIntegrationResult:
    values: dict[str, object] = {
        "request_id": "int-req-1041",
        "resolution": _resolution(),
        "composition": _composition(),
        "profile": _profile(),
        "cognitive_result": None,
        "agent_result": None,
        "decisions": (_decision(),),
        "domain_trace_id": None,
        "agent_trace_id": None,
        "blocked": True,
    }
    values.update(overrides)
    return DomainAgentRuntimeIntegrationResult(**values)


# ── Decision code surface ─────────────────────────────────────────────────────


def test_decision_code_enum_exposes_all_required_codes() -> None:
    assert tuple(code.name for code in DomainAgentRuntimeDecisionCode) == (
        ALL_DECISION_CODES
    )


# ── DomainActionBudget ────────────────────────────────────────────────────────


def test_domain_action_budget_accepts_valid_ceilings() -> None:
    budget = _budget(
        maximum_operations=5,
        maximum_iterations=3,
        maximum_questions=2,
        maximum_external_calls=1,
        maximum_duration_seconds=600,
        maximum_cost=Decimal("10.50"),
        metadata={"origin": "domain-policy"},
    )
    assert budget.domain_id == "domain:university"
    assert budget.maximum_operations == 5
    assert budget.maximum_cost == Decimal("10.50")


def test_domain_action_budget_rejects_blank_domain_id() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        DomainActionBudget(domain_id="")


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("maximum_operations", True),
        ("maximum_operations", False),
        ("maximum_iterations", True),
        ("maximum_questions", False),
        ("maximum_external_calls", True),
        ("maximum_duration_seconds", False),
    ),
)
def test_domain_action_budget_rejects_boolean_ceilings(
    field_name: str, value: bool
) -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _budget(**{field_name: value})


@pytest.mark.parametrize(
    "field_name",
    (
        "maximum_operations",
        "maximum_iterations",
        "maximum_questions",
        "maximum_external_calls",
        "maximum_duration_seconds",
    ),
)
def test_domain_action_budget_rejects_negative_integer_ceilings(
    field_name: str,
) -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _budget(**{field_name: -1})


def test_domain_action_budget_rejects_non_finite_cost() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _budget(maximum_cost=Decimal("NaN"))
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _budget(maximum_cost=Decimal("Infinity"))


def test_domain_action_budget_rejects_negative_cost() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _budget(maximum_cost=Decimal("-0.01"))


def test_domain_action_budget_rejects_non_string_metadata_keys() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _budget(metadata={1: "value"})


@pytest.mark.parametrize("key", ("api_key", "password", "auth_token", "client_secret"))
def test_domain_action_budget_rejects_secret_metadata(key: str) -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _budget(metadata={key: TEST_METADATA_VALUE})


def test_domain_action_budget_metadata_is_deeply_immutable() -> None:
    nested = {"layer": {"inner": "value"}}
    budget = _budget(metadata=nested)
    assert isinstance(budget.metadata, MappingProxyType)
    assert isinstance(budget.metadata["layer"], MappingProxyType)
    with pytest.raises(TypeError):
        budget.metadata["layer"]["inner"] = "mutated"  # type: ignore[index]
    with pytest.raises(TypeError):
        budget.metadata["new"] = "mutated"  # type: ignore[index]


def test_domain_action_budget_serialization_is_deterministic_and_json_safe() -> None:
    first = _budget(
        maximum_operations=5,
        maximum_cost=Decimal("10.50"),
        metadata={"b": 2, "a": 1},
    )
    second = _budget(
        maximum_operations=5,
        maximum_cost=Decimal("10.50"),
        metadata={"a": 1, "b": 2},
    )
    first_json = json.dumps(first.to_dict(), sort_keys=True)
    second_json = json.dumps(second.to_dict(), sort_keys=True)
    assert first_json == second_json
    assert json.loads(first_json)["maximum_cost"] == "10.50"


def test_domain_action_budget_has_no_mutation_or_increase_api() -> None:
    forbidden = ("increase", "add", "consume", "reserve", "set_limit", "reset")
    for attribute in dir(DomainActionBudget):
        assert not any(token in attribute.lower() for token in forbidden), attribute


# ── DomainAgentRuntimeDecision ────────────────────────────────────────────────


def test_decision_accepts_valid_record() -> None:
    decision = _decision()
    assert decision.code is DomainAgentRuntimeDecisionCode.DOMAIN_RESOLVED
    assert decision.reason_codes == ("explicit_domain_selected",)


def test_decision_rejects_blank_subject_id() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _decision(subject_id="")


def test_decision_rejects_invalid_code() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _decision(code="NOT_A_CODE")


def test_decision_rejects_blank_or_duplicate_reason_codes() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _decision(reason_codes=("",))
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _decision(reason_codes=("same", "same"))


def test_decision_rejects_blank_or_duplicate_related_ids() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _decision(related_ids=("",))
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _decision(related_ids=("dup", "dup"))


def test_decision_rejects_secret_metadata() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _decision(metadata={"access_token": TEST_METADATA_VALUE})


@pytest.mark.parametrize("key", HIDDEN_REASONING_KEYS)
def test_decision_rejects_hidden_reasoning_metadata(key: str) -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _decision(metadata={key: TEST_METADATA_VALUE})


def test_decision_serialization_is_deterministic_and_json_safe() -> None:
    first = _decision(metadata={"b": 2, "a": 1})
    second = _decision(metadata={"a": 1, "b": 2})
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(
        second.to_dict(), sort_keys=True
    )


# ── DomainAgentRuntimeIntegrationRequest ──────────────────────────────────────


def test_integration_request_accepts_canonical_objects() -> None:
    request = _integration_request()
    assert request.request_id == "int-req-1041"
    assert request.force_domain_reevaluation is False
    assert request.cognitive_resources == ()
    assert request.domain_budget is None


def test_integration_request_rejects_blank_request_id() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_request(request_id="")


def test_integration_request_requires_exact_canonical_context_type() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_request(resolution_context="res-ctx-1041")


def test_integration_request_requires_exact_canonical_agent_request_type() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_request(agent_request={"request_id": "req-1041"})


def test_integration_request_rejects_wrong_budget_type() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_request(domain_budget={"domain_id": "domain:university"})


def test_integration_request_rejects_non_bool_reevaluation_flag() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_request(force_domain_reevaluation=1)


def test_integration_request_rejects_goal_identity_conflict() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_request(
            resolution_context=_resolution_context(goal_id="goal-other"),
        )


def test_integration_request_rejects_actor_identity_conflict() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_request(
            resolution_context=_resolution_context(actor="actor-elsewhere"),
        )


def test_integration_request_allows_consistent_identity() -> None:
    request = _integration_request(
        resolution_context=_resolution_context(goal_id="goal-1041", actor="actor-1041"),
    )
    assert request.resolution_context.goal_id == "goal-1041"


def test_integration_request_metadata_is_immutable_and_secret_safe() -> None:
    request = _integration_request(metadata={"surface": "integration-test"})
    assert isinstance(request.metadata, MappingProxyType)
    with pytest.raises(TypeError):
        request.metadata["surface"] = "mutated"  # type: ignore[index]
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_request(metadata={"bearer": TEST_METADATA_VALUE})


# ── DomainAgentRuntimeIntegrationResult ───────────────────────────────────────


def test_integration_result_accepts_blocked_result_without_agent_result() -> None:
    result = _integration_result()
    assert result.blocked is True
    assert result.agent_result is None


def test_integration_result_requires_agent_result_when_not_blocked() -> None:
    from cmm.agent_runtime.agent_runtime_integration_contracts import (
        IntegratedAgentExecutionResult,
    )
    from cmm.agent_runtime.agent_runtime_integration_enums import (
        IntegrationExecutionState,
    )

    agent_result = IntegratedAgentExecutionResult(
        execution_id="exec-1041",
        request_id="req-1041",
        goal_id="goal-1041",
        final_state=IntegrationExecutionState.COMPLETED,
    )
    result = _integration_result(
        agent_result=agent_result,
        blocked=False,
        decisions=(
            _decision(code=DomainAgentRuntimeDecisionCode.DOMAIN_RUNTIME_COMPLETED),
        ),
    )
    assert result.agent_result is agent_result


def test_integration_result_requires_agent_result_when_not_blocked_and_missing() -> (
    None
):
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_result(blocked=False)


def test_integration_result_requires_exact_canonical_resolution_type() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_result(resolution="res-result-1041")


def test_integration_result_requires_exact_canonical_composition_type() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_result(composition="composition-1041")


def test_integration_result_requires_exact_canonical_profile_type() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_result(profile="resolved-profile-1041")


def test_integration_result_rejects_duplicate_decisions() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_result(decisions=(_decision(), _decision()))


def test_integration_result_rejects_duplicate_memory_binding_ids() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_result(memory_binding_ids=("binding-1", "binding-1"))


def test_integration_result_rejects_blank_trace_ids() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_result(domain_trace_id="")
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_result(agent_trace_id="")


def test_integration_result_rejects_secret_metadata() -> None:
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        _integration_result(metadata={"private_key": TEST_METADATA_VALUE})


def test_integration_result_decisions_are_immutable() -> None:
    result = _integration_result()
    with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
        result.decisions[0].subject_id = "mutated"  # type: ignore[misc]
