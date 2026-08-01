from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive import (
    InMemoryReasoningRuleRegistry,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
)
from cmm.domains import (
    DefaultDomainProfileResolver,
    DefaultDomainRuleSelector,
    DomainComposition,
    DomainCompositionItem,
    DomainCompositionStatus,
    DomainId,
    DomainProfileDefinition,
    DomainProfileResolutionRequest,
    DomainRuleSelectionStatus,
    EffectiveReasoningProfile,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


class Rule:
    def __init__(self, rule_id: str, *, domain: str | None = None, priority: int = 10,
                 status: str = "enabled", permissions: tuple[str, ...] = ()) -> None:
        self.definition = ReasoningRuleDefinition(
            id=rule_id, name=rule_id.replace(".", "_").title(), version="1.0.0",
            scope="domain" if domain else "global", domain_id=domain,
            category="safety" if rule_id.startswith("security.") else "epistemic",
            status=status, priority=priority, required_permissions=permissions,
            risk_level="high" if permissions else "low",
        )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        return ReasoningRuleResult(
            rule_id=self.definition.id, rule_name=self.definition.name,
            rule_version=self.definition.version, domain_id=self.definition.domain_id,
            status="applied", started_at=context.timestamp, completed_at=context.timestamp,
        )


def profile(*, required: tuple[str, ...] = (), optional: tuple[str, ...] = (),
            prohibited: tuple[str, ...] = (), permissions: tuple[str, ...] | None = None,
            supporting: tuple[str, ...] = ()):
    resolver = DefaultDomainProfileResolver(
        clock=lambda: NOW, id_factory=lambda: "resolution-1",
        profile_id_factory=lambda: "resolved-profile-1", trace_id_factory=lambda: "trace-1",
    )
    return resolver.resolve(
        request=DomainProfileResolutionRequest(
            id="request-1", primary_domain=DomainId("health"),
            supporting_domains=tuple(DomainId(item) for item in supporting),
        ),
        global_profile=DomainProfileDefinition(id="global", domain_id=DomainId("general"), profile_name="GeneralProfile"),
        primary_profile=DomainProfileDefinition(
            id="health", domain_id=DomainId("health"), profile_name="HealthProfile",
            required_rules=required, optional_rules=optional, prohibited_rules=prohibited,
            permissions=permissions,
        ),
        supporting_profiles=tuple(
            DomainProfileDefinition(
                id=f"support-{item}", domain_id=DomainId(item), profile_name=f"{item.title()}Profile"
            ) for item in supporting
        ),
    ).profile


def selector() -> DefaultDomainRuleSelector:
    return DefaultDomainRuleSelector(clock=lambda: NOW, id_factory=lambda: "plan-1")


def test_required_optional_prohibited_and_global_order() -> None:
    registry = InMemoryReasoningRuleRegistry()
    for rule in (
        Rule("global.base", priority=1), Rule("security.guard", priority=1),
        Rule("health.required", domain="domain:health", priority=2),
        Rule("health.optional", domain="domain:health", priority=99),
    ):
        registry.register(rule)
    plan = selector().select(
        registry=registry,
        profile=profile(required=("health.required",), optional=("health.optional",)),
        global_mandatory_rules=("global.base",), security_rules=("security.guard",),
    )
    assert plan.status is DomainRuleSelectionStatus.READY
    assert [r.definition.id for r in plan.selected_rules] == [
        "global.base", "security.guard", "health.required", "health.optional"
    ]


def test_optional_prohibited_is_omitted_and_missing_optional_is_partial() -> None:
    registry = InMemoryReasoningRuleRegistry()
    registry.register(Rule("health.optional", domain="domain:health"))
    plan = selector().select(
        registry=registry,
        profile=profile(optional=("health.optional", "health.missing"), prohibited=("health.optional",)),
    )
    assert plan.status is DomainRuleSelectionStatus.PARTIAL
    assert plan.selected_rules == ()
    assert set(plan.omitted_rule_ids) == {"health.optional", "health.missing"}


def test_required_missing_disabled_or_permission_denied_blocks() -> None:
    for registry in (
        InMemoryReasoningRuleRegistry(),
        _registry(Rule("health.required", domain="domain:health", status="disabled")),
        _registry(Rule("health.required", domain="domain:health", permissions=("health.read",))),
    ):
        plan = selector().select(
            registry=registry, profile=profile(required=("health.required",)),
            effective_permissions=(),
        )
        assert plan.status is DomainRuleSelectionStatus.BLOCKED
        assert plan.blocked_rule_ids == ("health.required",)


def _registry(*rules: Rule) -> InMemoryReasoningRuleRegistry:
    registry = InMemoryReasoningRuleRegistry()
    for rule in rules:
        registry.register(rule)
    return registry


def test_wrong_domain_blocks_required_and_primary_precedes_supporting() -> None:
    wrong = selector().select(
        registry=_registry(Rule("project.rule", domain="domain:project")),
        profile=profile(required=("project.rule",)),
    )
    assert wrong.status is DomainRuleSelectionStatus.BLOCKED

    resolved = profile(required=("health.rule", "project.rule"), supporting=("project",))
    plan = selector().select(
        registry=_registry(
            Rule("project.rule", domain="domain:project", priority=10),
            Rule("health.rule", domain="domain:health", priority=10),
        ),
        profile=resolved,
    )
    assert [r.definition.id for r in plan.selected_rules] == ["health.rule", "project.rule"]


def test_deduplication_preserves_multiple_sources_and_exact_version() -> None:
    registry = _registry(Rule("global.base"))
    plan = selector().select(
        registry=registry, profile=profile(optional=("global.base@1.0.0",)),
        global_mandatory_rules=("global.base",), requested_rule_ids=("global.base",),
    )
    assert len(plan.selected_rules) == 1
    assert len(plan.selected_rules[0].sources) == 3


def test_required_prohibited_from_composition_blocks_and_global_is_preserved() -> None:
    registry = _registry(Rule("global.base"), Rule("health.required", domain="domain:health"))
    resolved = profile(prohibited=("health.required", "global.base"))
    composition = DomainComposition(
        id="composition", resolution_id="resolution", status=DomainCompositionStatus.COMPOSED,
        primary_domain=DomainId("health"),
        effective_profile=EffectiveReasoningProfile(
            base_profile="HealthProfile", required_rules=("health.required",),
            contributing_domains=(DomainId("health"),),
        ),
        composed_at=NOW,
    )
    plan = selector().select(
        registry=registry, profile=resolved, composition=composition,
        global_mandatory_rules=("global.base",),
    )
    assert plan.status is DomainRuleSelectionStatus.BLOCKED
    assert set(plan.blocked_rule_ids) == {"global.base", "health.required"}
    assert [item.definition.id for item in plan.selected_rules] == ["global.base"]
    assert {conflict.code for conflict in plan.conflicts} == {
        "GLOBAL_MANDATORY_RULE_PROHIBITED", "REQUIRED_RULE_PROHIBITED"
    }


def test_optional_disabled_permission_and_wrong_domain_are_partial_with_codes() -> None:
    registry = _registry(
        Rule("health.disabled", domain="domain:health", status="disabled"),
        Rule("health.permission", domain="domain:health", permissions=("health.read",)),
        Rule("project.wrong", domain="domain:project"),
    )
    plan = selector().select(
        registry=registry,
        profile=profile(optional=("health.disabled", "health.permission", "project.wrong")),
        effective_permissions=(),
    )
    assert plan.status is DomainRuleSelectionStatus.PARTIAL
    assert set(plan.omitted_rule_ids) == {"health.disabled", "health.permission", "project.wrong"}
    codes = {decision.rule_id: decision.code.value for decision in plan.decisions}
    assert codes == {
        "health.disabled": "rule_disabled",
        "health.permission": "permission_missing",
        "project.wrong": "domain_mismatch",
    }
    assert plan.missing_permissions == ("health.read",)


def test_composed_rules_are_selected_with_original_10_8_provenance() -> None:
    composed_item = DomainCompositionItem(
        category="rules",
        identifier="project.rule",
        contributing_domains=(DomainId("project"), DomainId("health")),
        primary_contributor=DomainId("project"),
        precedence=2,
        metadata={"origin": "phase-10.8"},
    )
    composition = DomainComposition(
        id="composition", resolution_id="resolution", status="composed",
        primary_domain=DomainId("health"), supporting_domains=(DomainId("project"),),
        rules=(composed_item,), composed_at=NOW,
    )
    plan = selector().select(
        registry=_registry(Rule("project.rule", domain="domain:project")),
        profile=profile(supporting=("project",)),
        composition=composition,
    )
    assert [item.definition.id for item in plan.selected_rules] == ["project.rule"]
    source = plan.selected_rules[0].sources[0]
    assert source.source.value == "composition"
    assert source.domain_id == "domain:project"
    assert source.precedence == 2
    assert source.metadata["contributing_domains"] == (
        "domain:project", "domain:health"
    )
