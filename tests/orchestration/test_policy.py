"""Phase 11.2 — restrictive orchestration policy tests.

The policy evaluates whether a proposed route may proceed.  It is not a new
authorization system: it may only preserve or narrow the authority that
canonical evidence already established.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from cmm.orchestration.contracts import (
    AgentRouteDecision,
    DomainRouteDecision,
    ExecutionRoute,
    IntentKind,
    IntentResolution,
    OrchestrationChannel,
    OrchestrationRequest,
    PolicyDisposition,
    ResolvedContext,
)
from cmm.orchestration.policy import (
    DefaultOrchestrationPolicy,
    OrchestrationConfiguration,
    OrchestrationPolicy,
)

POLICY_MODULE = (
    Path(__file__).resolve().parents[2] / "cmm" / "orchestration" / "policy.py"
)

ALL_CHANNELS = (
    OrchestrationChannel.CONVERSATION,
    OrchestrationChannel.CLI,
    OrchestrationChannel.INTERNAL,
    OrchestrationChannel.API,
)


def _configuration(**overrides: object) -> OrchestrationConfiguration:
    values: dict[str, object] = {"allowed_channels": ALL_CHANNELS}
    values.update(overrides)
    return OrchestrationConfiguration(**values)  # type: ignore[arg-type]


def _request(channel: OrchestrationChannel = OrchestrationChannel.CONVERSATION):
    return OrchestrationRequest(
        request_id="request-1",
        user_id="user-1",
        channel=channel,
        session_id="session-1",
    )


def _intent(kind: IntentKind) -> IntentResolution:
    return IntentResolution(
        intent=kind, needs_clarification=False, source_kind="structured_input"
    )


def _domain(
    *,
    disposition: str | None = None,
    approval_refs: tuple[str, ...] = (),
    supporting: tuple[str, ...] = (),
) -> DomainRouteDecision:
    return DomainRouteDecision(
        status="resolved",
        primary_domain="domain:health",
        supporting_domains=supporting,
        permission_disposition=disposition,
        approval_refs=approval_refs,
    )


def _evaluate(
    *,
    intent: IntentKind = IntentKind.QUESTION,
    channel: OrchestrationChannel = OrchestrationChannel.CONVERSATION,
    domain: DomainRouteDecision | None = None,
    route: AgentRouteDecision | None = None,
    policy: DefaultOrchestrationPolicy | None = None,
):
    return (policy or DefaultOrchestrationPolicy()).evaluate(
        request=_request(channel),
        intent=_intent(intent),
        context=ResolvedContext(request_id="request-1", stage="domain"),
        domain=domain or _domain(),
        route=route or AgentRouteDecision(route=ExecutionRoute.DIRECT_RESPONSE),
    )


# ── Configuration ────────────────────────────────────────────────────────────


def test_policy_satisfies_its_protocol() -> None:
    assert isinstance(DefaultOrchestrationPolicy(), OrchestrationPolicy)


def test_default_configuration_allows_every_documented_channel() -> None:
    configuration = OrchestrationConfiguration(allowed_channels=ALL_CHANNELS)

    assert configuration.allowed_channels == ALL_CHANNELS
    assert configuration.decision_recording_required is True
    assert configuration.event_emission_required is True


def test_configuration_rejects_unknown_channel_values() -> None:
    with pytest.raises(TypeError):
        OrchestrationConfiguration(allowed_channels=("conversation",))  # type: ignore[arg-type]


def test_configuration_rejects_empty_channels() -> None:
    with pytest.raises(ValueError):
        OrchestrationConfiguration(allowed_channels=())


def test_configuration_rejects_duplicate_channels() -> None:
    with pytest.raises(ValueError):
        OrchestrationConfiguration(
            allowed_channels=(
                OrchestrationChannel.CLI,
                OrchestrationChannel.CLI,
            )
        )


def test_configuration_requires_decision_recording() -> None:
    with pytest.raises(ValueError):
        _configuration(decision_recording_required=False)


def test_configuration_requires_event_emission() -> None:
    with pytest.raises(ValueError):
        _configuration(event_emission_required=False)


def test_configuration_is_immutable() -> None:
    from dataclasses import FrozenInstanceError

    configuration = _configuration()

    with pytest.raises(FrozenInstanceError):
        configuration.allowed_channels = ()  # type: ignore[misc]


# ── Precedence ───────────────────────────────────────────────────────────────


def test_canonical_deny_blocks_the_route() -> None:
    decision = _evaluate(domain=_domain(disposition="deny"))

    assert decision.disposition is PolicyDisposition.DENY
    assert "POLICY_CANONICAL_DENY" in decision.reason_codes


def test_canonical_deny_cannot_be_widened_by_the_channel() -> None:
    policy = DefaultOrchestrationPolicy(configuration=_configuration())

    decision = _evaluate(
        policy=policy,
        domain=_domain(disposition="deny"),
        channel=OrchestrationChannel.CONVERSATION,
    )

    assert decision.disposition is PolicyDisposition.DENY


def test_canonical_deny_outranks_every_other_signal() -> None:
    decision = _evaluate(
        intent=IntentKind.GOAL,
        domain=_domain(disposition="deny", approval_refs=("approval-1",)),
        route=AgentRouteDecision(
            route=ExecutionRoute.AUTONOMOUS_AGENT, agent_id="agent.alpha"
        ),
    )

    assert decision.disposition is PolicyDisposition.DENY


def test_canonical_approval_requirement_is_preserved() -> None:
    decision = _evaluate(
        domain=_domain(
            disposition="approval_required", approval_refs=("requirement-1",)
        )
    )

    assert decision.disposition is PolicyDisposition.REQUIRE_APPROVAL
    assert decision.approval_refs == ("requirement-1",)
    assert "POLICY_APPROVAL_REQUIRED" in decision.reason_codes


def test_canonical_approval_requirement_cannot_become_allow() -> None:
    policy = DefaultOrchestrationPolicy(configuration=_configuration())

    decision = _evaluate(
        policy=policy,
        domain=_domain(
            disposition="approval_required", approval_refs=("requirement-1",)
        ),
    )

    assert decision.disposition is not PolicyDisposition.ALLOW_ROUTE


def test_supporting_domain_deny_cannot_be_widened() -> None:
    decision = _evaluate(
        domain=_domain(disposition="deny", supporting=("domain:university",))
    )

    assert decision.disposition is PolicyDisposition.DENY


def test_disallowed_channel_is_denied() -> None:
    policy = DefaultOrchestrationPolicy(
        configuration=_configuration(
            allowed_channels=(OrchestrationChannel.CONVERSATION,)
        )
    )

    decision = _evaluate(policy=policy, channel=OrchestrationChannel.API)

    assert decision.disposition is PolicyDisposition.DENY
    assert "POLICY_CHANNEL_NOT_ALLOWED" in decision.reason_codes


def test_allowed_channel_does_not_add_authority() -> None:
    policy = DefaultOrchestrationPolicy(
        configuration=_configuration(allowed_channels=ALL_CHANNELS)
    )

    decision = _evaluate(policy=policy, channel=OrchestrationChannel.API)

    assert decision.disposition is PolicyDisposition.ALLOW_ROUTE


def test_human_escalation_route_escalates() -> None:
    decision = _evaluate(
        intent=IntentKind.CONFIGURATION_CHANGE,
        route=AgentRouteDecision(route=ExecutionRoute.HUMAN_ESCALATION),
    )

    assert decision.disposition is PolicyDisposition.ESCALATE
    assert "POLICY_ROUTE_ESCALATION" in decision.reason_codes


def test_unsupported_route_escalates() -> None:
    decision = _evaluate(route=AgentRouteDecision(route=ExecutionRoute.NONE))

    assert decision.disposition is PolicyDisposition.ESCALATE
    assert "POLICY_ROUTE_UNSUPPORTED" in decision.reason_codes


# ── Missing canonical authority evidence ─────────────────────────────────────


@pytest.mark.parametrize(
    "route",
    [
        ExecutionRoute.OPERATION,
        ExecutionRoute.WORKFLOW,
    ],
)
def test_side_effecting_route_without_evidence_escalates(
    route: ExecutionRoute,
) -> None:
    decision = _evaluate(route=AgentRouteDecision(route=route))

    assert decision.disposition is PolicyDisposition.ESCALATE
    assert "POLICY_MISSING_AUTHORITY_EVIDENCE" in decision.reason_codes


def test_autonomous_route_without_evidence_escalates() -> None:
    decision = _evaluate(
        intent=IntentKind.GOAL,
        route=AgentRouteDecision(
            route=ExecutionRoute.AUTONOMOUS_AGENT, agent_id="agent.alpha"
        ),
    )

    assert decision.disposition is PolicyDisposition.ESCALATE


def test_side_effecting_route_with_allow_evidence_is_allowed() -> None:
    decision = _evaluate(
        route=AgentRouteDecision(route=ExecutionRoute.OPERATION),
        domain=_domain(disposition="allow"),
    )

    assert decision.disposition is PolicyDisposition.ALLOW_ROUTE
    assert "POLICY_ALLOWED" in decision.reason_codes


def test_direct_response_needs_no_authority_evidence() -> None:
    decision = _evaluate(route=AgentRouteDecision(route=ExecutionRoute.DIRECT_RESPONSE))

    assert decision.disposition is PolicyDisposition.ALLOW_ROUTE


def test_unknown_evidence_value_fails_closed_for_side_effects() -> None:
    decision = _evaluate(
        route=AgentRouteDecision(route=ExecutionRoute.OPERATION),
        domain=_domain(disposition="unexpected"),
    )

    assert decision.disposition is PolicyDisposition.ESCALATE


# ── Determinism and shape ────────────────────────────────────────────────────


def test_evaluation_is_deterministic() -> None:
    policy = DefaultOrchestrationPolicy()
    domain = _domain(disposition="allow")

    first = _evaluate(policy=policy, domain=domain).to_dict()
    second = _evaluate(policy=policy, domain=domain).to_dict()

    assert first == second


def test_policy_requires_real_inputs() -> None:
    policy = DefaultOrchestrationPolicy()

    with pytest.raises(TypeError):
        policy.evaluate(
            request=object(),  # type: ignore[arg-type]
            intent=_intent(IntentKind.QUESTION),
            context=ResolvedContext(request_id="request-1", stage="domain"),
            domain=_domain(),
            route=AgentRouteDecision(route=ExecutionRoute.DIRECT_RESPONSE),
        )


def test_policy_module_defines_no_policy_engine() -> None:
    tree = ast.parse(POLICY_MODULE.read_text())

    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(
            token in node.name for token in ("Registry", "Rule", "Engine", "Database")
        )
    ]

    assert not offenders, f"policy must not add a policy engine: {offenders}"
