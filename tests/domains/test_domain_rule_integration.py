from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive import ReasoningRuleContext
from cmm.domains import (
    DefaultDomainProfileResolver,
    DefaultDomainRuleExecutor,
    DefaultDomainRuleSelector,
    DomainId,
    DomainProfileDefinition,
    DomainProfileOverlay,
    DomainProfileResolutionRequest,
    DomainProfileSource,
    build_initial_reasoning_rule_catalog,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_resolved_profile_becomes_real_execution_without_reresolution() -> None:
    profile = DefaultDomainProfileResolver(
        clock=lambda: NOW, id_factory=lambda: "resolution", profile_id_factory=lambda: "profile",
        trace_id_factory=lambda: "trace",
    ).resolve(
        request=DomainProfileResolutionRequest(id="request", primary_domain=DomainId("health")),
        global_profile=DomainProfileDefinition(id="g", domain_id=DomainId("general"), profile_name="GeneralProfile"),
        primary_profile=DomainProfileDefinition(
            id="h", domain_id=DomainId("health"), profile_name="HealthProfile",
            required_rules=("health.red_flags",), optional_rules=("global.preserve_provenance",),
            permissions=("knowledge.health.read",),
        ),
    ).profile
    registry = build_initial_reasoning_rule_catalog()
    plan = DefaultDomainRuleSelector(clock=lambda: NOW, id_factory=lambda: "plan").select(
        registry=registry, profile=profile,
        global_mandatory_rules=("global.distinguish_fact_inference_hypothesis",),
        security_rules=("security.respect_sensitivity",),
        effective_permissions=("knowledge.health.read",),
    )
    result = DefaultDomainRuleExecutor(clock=lambda: NOW, id_factory=lambda: "execution").execute(
        plan=plan,
        context=ReasoningRuleContext(
            reasoning_id="r", active_domains=("domain:health",), primary_domain="domain:health",
            effective_permissions=("knowledge.health.read",), timestamp=NOW,
        ),
        registry=registry,
    )
    assert [item.rule_id for item in result.rule_results] == [
        "global.distinguish_fact_inference_hypothesis",
        "security.respect_sensitivity",
        "health.red_flags",
        "global.preserve_provenance",
    ]


def test_resolved_overlay_affects_selection_without_recomposition() -> None:
    resolution = DefaultDomainProfileResolver(
        clock=lambda: NOW,
        id_factory=lambda: "resolution",
        profile_id_factory=lambda: "profile",
        trace_id_factory=lambda: "trace",
    ).resolve(
        request=DomainProfileResolutionRequest(
            id="request",
            primary_domain=DomainId("health"),
        ),
        global_profile=DomainProfileDefinition(
            id="g",
            domain_id=DomainId("general"),
            profile_name="GeneralProfile",
        ),
        primary_profile=DomainProfileDefinition(
            id="h",
            domain_id=DomainId("health"),
            profile_name="HealthProfile",
        ),
        overlays=(
            DomainProfileOverlay(
                id="policy-overlay",
                source=DomainProfileSource.GLOBAL_POLICY,
                optional_rules=("global.preserve_provenance",),
            ),
        ),
    )
    registry = build_initial_reasoning_rule_catalog()

    plan = DefaultDomainRuleSelector(
        clock=lambda: NOW,
        id_factory=lambda: "plan",
    ).select(registry=registry, profile=resolution.profile)

    assert [item.definition.id for item in plan.selected_rules] == [
        "global.preserve_provenance"
    ]
