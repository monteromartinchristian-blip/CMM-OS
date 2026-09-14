from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive import (
    InMemoryReasoningRuleRegistry,
    ReasoningRule,
    ReasoningRuleCategory,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleRegistry,
    ReasoningRuleRegistryError,
    ReasoningRuleResult,
    ReasoningRuleStatus,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


class Rule:
    def __init__(self, rule_id: str, version: str, *, status: str = "enabled", domain_id: str | None = None) -> None:
        self.calls = 0
        self._definition = ReasoningRuleDefinition(
            id=rule_id,
            name="Rule",
            version=version,
            scope="domain" if domain_id else "global",
            domain_id=domain_id,
            category="epistemic",
            status=status,
            priority=10,
            risk_level="low",
        )

    @property
    def definition(self) -> ReasoningRuleDefinition:
        return self._definition

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        self.calls += 1
        return ReasoningRuleResult(
            rule_id=self.definition.id,
            rule_name=self.definition.name,
            rule_version=self.definition.version,
            domain_id=self.definition.domain_id,
            status="applied",
            started_at=context.timestamp,
            completed_at=context.timestamp,
        )


def test_registry_protocol_and_registration_does_not_execute() -> None:
    registry = InMemoryReasoningRuleRegistry()
    rule = Rule("global.rule", "1.0.0")
    assert isinstance(registry, ReasoningRuleRegistry)
    assert isinstance(rule, ReasoningRule)
    registry.register(rule)
    assert rule.calls == 0
    assert registry.get("global.rule", "1.0.0") is rule


def test_active_version_uses_semver_and_skips_disabled() -> None:
    registry = InMemoryReasoningRuleRegistry()
    for version, status in (("1.9.0", "enabled"), ("1.10.0", "enabled"), ("2.0.0", "disabled")):
        registry.register(Rule("global.rule", version, status=status))
    assert registry.resolve("global.rule").definition.version == "1.10.0"
    assert [d.version for d in registry.inspect_definitions()] == ["1.9.0", "1.10.0", "2.0.0"]
    assert [r.definition.version for r in registry.list_enabled()] == ["1.9.0", "1.10.0"]


def test_registry_filters_and_isolation_are_deterministic() -> None:
    registry = InMemoryReasoningRuleRegistry()
    registry.register(Rule("project.rule", "1.0.0", domain_id="domain:project"))
    registry.register(Rule("global.rule", "1.0.0"))
    assert [r.definition.id for r in registry.list_all()] == ["global.rule", "project.rule"]
    assert registry.list_by_domain("domain:project")[0].definition.id == "project.rule"
    assert registry.list_by_scope("global")[0].definition.id == "global.rule"
    assert registry.list_by_category("epistemic") == registry.list_all()
    assert InMemoryReasoningRuleRegistry().list_all() == ()


def test_registry_rejects_collision_and_superficial_object() -> None:
    registry = InMemoryReasoningRuleRegistry()
    registry.register(Rule("global.rule", "1.0.0"))
    with pytest.raises(ReasoningRuleRegistryError):
        registry.register(Rule("global.rule", "1.0.0"))
    with pytest.raises(ReasoningRuleRegistryError):
        registry.register(object())  # type: ignore[arg-type]
    class WrongSignature:
        definition = Rule("global.other", "1.0.0").definition

        def evaluate(self) -> ReasoningRuleResult:
            raise AssertionError("must not execute")

    with pytest.raises(ReasoningRuleRegistryError, match="signature"):
        registry.register(WrongSignature())  # type: ignore[arg-type]
    registry.unregister("global.rule", "1.0.0")
    assert registry.get("global.rule", "1.0.0") is None


@pytest.mark.parametrize(
    "rule_type",
    [
        type(
            "VariadicPositionalRule",
            (),
            {
                "definition": Rule("global.varargs", "1.0.0").definition,
                "evaluate": lambda self, context, *args: None,
            },
        ),
        type(
            "RequiredPositionalRule",
            (),
            {
                "definition": Rule("global.required_positional", "1.0.0").definition,
                "evaluate": lambda self, context, extra: None,
            },
        ),
        type(
            "RequiredKeywordOnlyRule",
            (),
            {
                "definition": Rule("global.required_keyword", "1.0.0").definition,
                "evaluate": lambda self, context, *, extra: None,
            },
        ),
    ],
)
def test_registry_rejects_incompatible_evaluate_signatures(rule_type: type) -> None:
    with pytest.raises(ReasoningRuleRegistryError, match="signature"):
        InMemoryReasoningRuleRegistry().register(rule_type())  # type: ignore[arg-type]


def test_registry_accepts_only_optional_additional_parameters() -> None:
    class OptionalParametersRule:
        definition = Rule("global.optional_parameters", "1.0.0").definition

        def evaluate(
            self,
            context: ReasoningRuleContext,
            mode: str = "safe",
            *,
            trace: bool = False,
        ) -> ReasoningRuleResult:
            raise AssertionError("registration must not execute the rule")

    registry = InMemoryReasoningRuleRegistry()
    rule = OptionalParametersRule()
    assert registry.register(rule) is rule  # type: ignore[arg-type]


def test_registry_category_and_status_filters_validate_enums() -> None:
    registry = InMemoryReasoningRuleRegistry()
    enabled = Rule("global.enabled", "1.0.0")
    disabled = Rule("global.disabled", "1.0.0", status="disabled")
    registry.register(enabled)
    registry.register(disabled)

    assert registry.list_by_category(ReasoningRuleCategory.EPISTEMIC) == (
        disabled,
        enabled,
    )
    assert registry.list_by_category("epistemic") == (disabled, enabled)
    assert registry.list_by_status(ReasoningRuleStatus.ENABLED) == (enabled,)
    assert registry.list_by_status("disabled") == (disabled,)

    with pytest.raises(ReasoningRuleRegistryError, match="category"):
        registry.list_by_category("unknown")
    with pytest.raises(ReasoningRuleRegistryError, match="status"):
        registry.list_by_status("unknown")


def test_registry_semver_handles_prerelease_and_numeric_precedence() -> None:
    registry = InMemoryReasoningRuleRegistry()
    for version in ("2.0.0-alpha.2", "2.0.0-alpha.10", "2.0.0"):
        registry.register(Rule("global.versioned", version))
    assert registry.resolve("global.versioned").definition.version == "2.0.0"
