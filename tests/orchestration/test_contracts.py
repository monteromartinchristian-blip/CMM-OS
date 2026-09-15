"""Phase 11.2 — public orchestration contract tests.

These tests freeze the Phase 11.2 boundary values: the enums, the request, the
collaborator results, the decision record and the orchestration result.  They
prove immutability, defensive copying, deterministic serialization and the
absence of any hidden-reasoning or memory-mutation surface.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from cmm.orchestration.contracts import (
    AgentRouteDecision,
    DomainRouteDecision,
    ExecutionRoute,
    IntentKind,
    IntentResolution,
    OrchestrationChannel,
    OrchestrationDecisionRecord,
    OrchestrationPolicyDecision,
    OrchestrationRequest,
    OrchestrationResult,
    OrchestrationStatus,
    PolicyDisposition,
    ResolvedContext,
)

FORBIDDEN_PUBLIC_FIELD_NAMES = (
    "chain_of_thought",
    "hidden_reasoning",
    "raw_reasoning",
    "reasoning_trace",
    "prompt",
    "provider_payload",
    "credentials",
    "credential",
    "secret",
    "memory_updates",
)

PUBLIC_CONTRACTS = (
    OrchestrationRequest,
    IntentResolution,
    ResolvedContext,
    DomainRouteDecision,
    AgentRouteDecision,
    OrchestrationPolicyDecision,
    OrchestrationDecisionRecord,
    OrchestrationResult,
)


def _request(**overrides: object) -> OrchestrationRequest:
    values: dict[str, object] = {
        "request_id": "request-1",
        "user_id": "user-1",
        "channel": OrchestrationChannel.CONVERSATION,
    }
    values.update(overrides)
    return OrchestrationRequest(**values)  # type: ignore[arg-type]


def _decision_record(**overrides: object) -> OrchestrationDecisionRecord:
    values: dict[str, object] = {
        "decision_id": "decision-1",
        "request_id": "request-1",
        "channel": OrchestrationChannel.CONVERSATION,
        "intent": IntentKind.QUESTION,
        "execution_route": ExecutionRoute.DIRECT_RESPONSE,
        "policy_disposition": PolicyDisposition.ALLOW_ROUTE,
    }
    values.update(overrides)
    return OrchestrationDecisionRecord(**values)  # type: ignore[arg-type]


# ── Enums ────────────────────────────────────────────────────────────────────


def test_intent_kind_values_are_frozen() -> None:
    assert {member.value for member in IntentKind} == {
        "question",
        "reflection",
        "command",
        "goal",
        "workflow_request",
        "information_update",
        "approval_response",
        "continuation",
        "cancellation",
        "configuration_change",
        "unknown",
    }


def test_channel_values_are_frozen() -> None:
    assert {member.value for member in OrchestrationChannel} == {
        "conversation",
        "cli",
        "internal",
        "api",
    }


def test_execution_route_values_are_frozen() -> None:
    assert {member.value for member in ExecutionRoute} == {
        "direct_response",
        "operation",
        "workflow",
        "autonomous_agent",
        "human_escalation",
        "none",
    }


def test_orchestration_status_values_are_frozen() -> None:
    assert {member.value for member in OrchestrationStatus} == {
        "routed",
        "needs_clarification",
        "blocked",
        "escalated",
        "cancelled",
        "failed",
    }


def test_policy_disposition_values_are_frozen() -> None:
    assert {member.value for member in PolicyDisposition} == {
        "allow_route",
        "require_approval",
        "escalate",
        "deny",
    }


# ── OrchestrationRequest ─────────────────────────────────────────────────────


def test_request_requires_non_empty_request_id() -> None:
    with pytest.raises(ValueError):
        _request(request_id="   ")


def test_request_requires_non_empty_user_id() -> None:
    with pytest.raises(ValueError):
        _request(user_id="")


def test_request_rejects_invalid_channel() -> None:
    with pytest.raises(TypeError):
        _request(channel="conversation")


def test_request_rejects_invalid_intent_hint() -> None:
    with pytest.raises(TypeError):
        _request(intent_hint="question")


def test_request_accepts_none_intent_hint() -> None:
    assert _request(intent_hint=None).intent_hint is None


def test_request_defensively_freezes_input_and_context() -> None:
    payload = {"question": "What changed?", "nested": {"tags": ["a", "b"]}}
    caller_context = {"session_domain": "general"}

    request = _request(input=payload, context=caller_context)

    payload["question"] = "mutated"
    payload["nested"]["tags"].append("c")
    caller_context["session_domain"] = "mutated"

    assert request.input["question"] == "What changed?"
    assert request.input["nested"]["tags"] == ("a", "b")
    assert request.context["session_domain"] == "general"
    with pytest.raises(TypeError):
        request.input["question"] = "nope"  # type: ignore[index]


def test_request_rejects_opaque_runtime_object() -> None:
    with pytest.raises(TypeError):
        _request(input={"client": object()})


def test_request_rejects_binary_payload() -> None:
    with pytest.raises(TypeError):
        _request(input={"blob": b"bytes"})


def test_request_rejects_non_string_mapping_key() -> None:
    with pytest.raises(TypeError):
        _request(input={1: "value"})


def test_request_freezes_capabilities() -> None:
    request = _request(requested_capabilities=["knowledge.read", "knowledge.read"])

    assert request.requested_capabilities == ("knowledge.read",)


def test_request_rejects_empty_capability() -> None:
    with pytest.raises(ValueError):
        _request(requested_capabilities=("  ",))


def test_request_normalizes_optional_references() -> None:
    request = _request(session_id="  session-1  ", bot_id="")

    assert request.session_id == "session-1"
    assert request.bot_id is None


def test_request_is_frozen() -> None:
    request = _request()

    with pytest.raises(FrozenInstanceError):
        request.request_id = "other"  # type: ignore[misc]


def test_request_serializes_to_safe_primitives() -> None:
    request = _request(
        session_id="session-1",
        input={"question": "What changed?"},
        requested_capabilities=("knowledge.read",),
        intent_hint=IntentKind.QUESTION,
    )

    payload = request.to_dict()

    assert payload == {
        "request_id": "request-1",
        "user_id": "user-1",
        "channel": "conversation",
        "session_id": "session-1",
        "bot_id": None,
        "input": {"question": "What changed?"},
        "context": {},
        "requested_capabilities": ["knowledge.read"],
        "intent_hint": "question",
    }
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


# ── Collaborator results ─────────────────────────────────────────────────────


def test_intent_resolution_defaults_are_fail_closed() -> None:
    resolution = IntentResolution(intent=IntentKind.UNKNOWN)

    assert resolution.needs_clarification is True
    assert resolution.reason_codes == ()
    assert resolution.to_dict() == {
        "intent": "unknown",
        "needs_clarification": True,
        "source_kind": "intent_hint",
        "reason_codes": [],
    }


def test_resolved_context_serializes_only_safe_refs() -> None:
    context = ResolvedContext(
        request_id="request-1",
        stage="base",
        session_ref="session-1",
        session_status="ACTIVE",
        session_revision=3,
    )

    assert context.to_dict() == {
        "request_id": "request-1",
        "stage": "base",
        "session_ref": "session-1",
        "session_status": "ACTIVE",
        "session_revision": 3,
        "context_refs": [],
        "domain_refs": [],
        "permission_refs": [],
        "missing_refs": [],
        "withheld_field_count": 0,
        "reason_codes": [],
    }


def test_resolved_context_rejects_unknown_stage() -> None:
    with pytest.raises(ValueError):
        ResolvedContext(request_id="request-1", stage="other")


def test_domain_route_decision_keeps_primary_and_supporting_identity() -> None:
    decision = DomainRouteDecision(
        status="resolved",
        primary_domain="domain:health",
        supporting_domains=("domain:university",),
    )

    assert decision.primary_domain == "domain:health"
    assert decision.supporting_domains == ("domain:university",)
    assert decision.to_dict()["supporting_domains"] == ["domain:university"]


def test_agent_route_decision_has_no_agent_when_not_selected() -> None:
    decision = AgentRouteDecision(route=ExecutionRoute.DIRECT_RESPONSE)

    assert decision.agent_id is None
    assert decision.to_dict() == {
        "route": "direct_response",
        "agent_id": None,
        "agent_version": None,
        "workflow_id": None,
        "reason_codes": [],
    }


def test_agent_route_decision_rejects_agent_for_non_agent_route() -> None:
    with pytest.raises(ValueError):
        AgentRouteDecision(route=ExecutionRoute.OPERATION, agent_id="agent.alpha")


def test_agent_route_decision_requires_agent_for_autonomous_route() -> None:
    with pytest.raises(ValueError):
        AgentRouteDecision(route=ExecutionRoute.AUTONOMOUS_AGENT)


def test_policy_decision_defaults_to_deny() -> None:
    decision = OrchestrationPolicyDecision(disposition=PolicyDisposition.DENY)

    assert decision.disposition is PolicyDisposition.DENY
    assert decision.approval_refs == ()


def test_policy_decision_rejects_unknown_disposition() -> None:
    with pytest.raises(TypeError):
        OrchestrationPolicyDecision(disposition="allow")


# ── Decision record ──────────────────────────────────────────────────────────


def test_decision_record_carries_safe_categorical_facts() -> None:
    record = _decision_record()

    payload = record.to_dict()

    assert payload["decision_id"] == "decision-1"
    assert payload["request_id"] == "request-1"
    assert payload["channel"] == "conversation"
    assert payload["intent"] == "question"
    assert payload["execution_route"] == "direct_response"
    assert payload["policy_disposition"] == "allow_route"
    assert payload["primary_domain"] is None
    assert payload["supporting_domains"] == []
    assert payload["selected_agent_id"] is None
    assert payload["workflow_id"] is None
    assert payload["approval_refs"] == []
    assert payload["reason_codes"] == []
    assert payload["trace_refs"] == []
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_decision_record_rejects_invalid_identifiers() -> None:
    with pytest.raises(ValueError):
        _decision_record(decision_id="")
    with pytest.raises(ValueError):
        _decision_record(request_id="   ")


def test_decision_record_has_no_raw_request_or_reasoning_field() -> None:
    names = set(OrchestrationDecisionRecord.__dataclass_fields__)

    for forbidden in FORBIDDEN_PUBLIC_FIELD_NAMES:
        assert forbidden not in names


# ── OrchestrationResult ──────────────────────────────────────────────────────


def test_result_contains_no_reasoning_trace_or_memory_updates_field() -> None:
    names = set(OrchestrationResult.__dataclass_fields__)

    for forbidden in FORBIDDEN_PUBLIC_FIELD_NAMES:
        assert forbidden not in names


@pytest.mark.parametrize("contract", PUBLIC_CONTRACTS, ids=lambda item: item.__name__)
def test_public_contracts_expose_no_forbidden_field(contract: type) -> None:
    names = set(contract.__dataclass_fields__)

    for forbidden in FORBIDDEN_PUBLIC_FIELD_NAMES:
        assert forbidden not in names


def test_result_serializes_safe_refs_only() -> None:
    result = OrchestrationResult(
        request_id="request-1",
        status=OrchestrationStatus.ROUTED,
        intent=IntentKind.QUESTION,
        primary_domain="domain:health",
        supporting_domains=("domain:university",),
        profile_id="health.default",
        route=ExecutionRoute.DIRECT_RESPONSE,
        decision_id="decision-1",
        trace_refs=("domain-resolution:1",),
        reason_codes=("DOMAIN_RESOLVED",),
    )

    payload = result.to_dict()

    assert payload["status"] == "routed"
    assert payload["intent"] == "question"
    assert payload["route"] == "direct_response"
    assert payload["decision_id"] == "decision-1"
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_result_rejects_unknown_status() -> None:
    with pytest.raises(TypeError):
        OrchestrationResult(request_id="request-1", status="completed")


def test_result_rejects_non_error_result_error_payload() -> None:
    with pytest.raises(TypeError):
        OrchestrationResult(
            request_id="request-1",
            status=OrchestrationStatus.FAILED,
            error={"code": "X"},
        )


def test_result_accepts_safe_error_result() -> None:
    from cmm.platform.contracts import ErrorResult

    result = OrchestrationResult(
        request_id="request-1",
        status=OrchestrationStatus.FAILED,
        error=ErrorResult(
            code="ORCHESTRATION_FAILED",
            message="Orchestration failed closed",
            category="orchestration",
            details={"request_id": "request-1"},
        ),
    )

    payload = result.to_dict()

    assert payload["error"]["code"] == "ORCHESTRATION_FAILED"
    assert payload["error"]["details"] == {"request_id": "request-1"}


def test_result_is_immutable() -> None:
    result = OrchestrationResult(
        request_id="request-1", status=OrchestrationStatus.ROUTED
    )

    with pytest.raises(FrozenInstanceError):
        result.status = OrchestrationStatus.FAILED  # type: ignore[misc]


def test_result_defaults_serialize_deterministically() -> None:
    result = OrchestrationResult(
        request_id="request-1", status=OrchestrationStatus.NEEDS_CLARIFICATION
    )

    assert result.to_dict() == {
        "request_id": "request-1",
        "status": "needs_clarification",
        "intent": "unknown",
        "primary_domain": None,
        "supporting_domains": [],
        "profile_id": None,
        "route": "none",
        "agent_id": None,
        "workflow_id": None,
        "approval_refs": [],
        "decision_id": None,
        "trace_refs": [],
        "reason_codes": [],
        "error": None,
    }


def test_decision_record_occurred_at_is_timezone_aware() -> None:
    record = _decision_record()

    assert record.occurred_at.tzinfo is not None
    assert isinstance(record.occurred_at, datetime)
    assert record.occurred_at <= datetime.now(timezone.utc)


def test_decision_record_rejects_naive_occurred_at() -> None:
    with pytest.raises(ValueError):
        _decision_record(occurred_at=datetime.fromisoformat("2026-01-01T00:00:00"))
