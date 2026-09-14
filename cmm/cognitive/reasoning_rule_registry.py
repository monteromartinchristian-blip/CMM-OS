"""Deterministic in-memory registry for common reasoning-rule implementations."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from cmm.cognitive.enums import (
    ReasoningRuleCategory,
    ReasoningRuleScope,
    ReasoningRuleStatus,
)
from cmm.cognitive.errors import ReasoningRuleRegistryError
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningRule,
    ReasoningRuleDefinition,
    _semver_key,
)


@dataclass(frozen=True, slots=True)
class ReasoningRuleRegistrySnapshot:
    """Immutable snapshot of the reasoning-rule registry state.

    ``rules`` is the canonical ordered tuple of registered rule objects.
    Each rule object carries its frozen ``definition`` and callable
    ``evaluate``; the tuple preserves exact identity and order.
    """

    rules: tuple[ReasoningRule, ...]


@runtime_checkable
class ReasoningRuleRegistry(Protocol):
    def register(self, rule: ReasoningRule) -> ReasoningRule: ...
    def unregister(self, rule_id: str, version: str) -> None: ...
    def get(self, rule_id: str, version: str) -> ReasoningRule | None: ...
    def resolve(self, rule_id: str) -> ReasoningRule | None: ...
    def list_all(self) -> tuple[ReasoningRule, ...]: ...
    def list_enabled(self) -> tuple[ReasoningRule, ...]: ...
    def list_by_scope(self, scope: ReasoningRuleScope | str) -> tuple[ReasoningRule, ...]: ...
    def list_by_domain(self, domain_id: str) -> tuple[ReasoningRule, ...]: ...
    def list_by_category(
        self, category: ReasoningRuleCategory | str
    ) -> tuple[ReasoningRule, ...]: ...
    def list_by_status(
        self, status: ReasoningRuleStatus | str
    ) -> tuple[ReasoningRule, ...]: ...
    def inspect_definitions(self) -> tuple[ReasoningRuleDefinition, ...]: ...
    def snapshot_state(self) -> ReasoningRuleRegistrySnapshot: ...
    def restore_state(self, snapshot: ReasoningRuleRegistrySnapshot) -> None: ...


def _validate_rule(rule: ReasoningRule) -> None:
    """Validate that a rule is registerable (canonical executability contract).

    Single source of truth for rule validity, shared by ``register()`` and
    ``restore_state()`` so a snapshot can never admit a rule that the normal
    registration contract would reject.  Side-effect free.
    """
    definition = getattr(rule, "definition", None)
    evaluate = getattr(rule, "evaluate", None)
    if not isinstance(definition, ReasoningRuleDefinition) or not callable(evaluate):
        raise ReasoningRuleRegistryError(
            "rule must expose a ReasoningRuleDefinition and callable evaluate",
            field="rule",
        )
    try:
        parameters = tuple(inspect.signature(evaluate).parameters.values())
    except (TypeError, ValueError) as exc:
        raise ReasoningRuleRegistryError(
            "rule evaluate signature cannot be inspected", field="rule"
        ) from exc
    positional = tuple(
        parameter
        for parameter in parameters
        if parameter.kind
        in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
    )
    has_varargs = any(
        parameter.kind is inspect.Parameter.VAR_POSITIONAL
        for parameter in parameters
    )
    required_additional = tuple(
        parameter
        for parameter in parameters[1:]
        if parameter.kind is not inspect.Parameter.VAR_KEYWORD
        and parameter.default is inspect.Parameter.empty
    )
    if not positional or has_varargs or required_additional:
        raise ReasoningRuleRegistryError(
            "rule evaluate signature must accept context and only optional additional parameters",
            field="rule",
        )


class InMemoryReasoningRuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[tuple[str, str], ReasoningRule] = {}

    def register(self, rule: ReasoningRule) -> ReasoningRule:
        _validate_rule(rule)
        definition = getattr(rule, "definition", None)
        key = (definition.id, definition.version)
        if key in self._rules:
            raise ReasoningRuleRegistryError(
                "rule id/version collision", field="version",
                details={"id": definition.id, "version": definition.version},
            )
        self._rules[key] = rule
        return rule

    def unregister(self, rule_id: str, version: str) -> None:
        self._rules.pop((rule_id, version), None)

    def get(self, rule_id: str, version: str) -> ReasoningRule | None:
        return self._rules.get((rule_id, version))

    def resolve(self, rule_id: str) -> ReasoningRule | None:
        matches = [
            rule for (candidate_id, _), rule in self._rules.items()
            if candidate_id == rule_id and rule.definition.status is ReasoningRuleStatus.ENABLED
        ]
        if not matches:
            return None
        return max(matches, key=lambda rule: _semver_key(rule.definition.version))

    @staticmethod
    def _sort(rules: list[ReasoningRule]) -> tuple[ReasoningRule, ...]:
        return tuple(sorted(rules, key=lambda rule: (rule.definition.id, _semver_key(rule.definition.version))))

    def list_all(self) -> tuple[ReasoningRule, ...]:
        return self._sort(list(self._rules.values()))

    def list_enabled(self) -> tuple[ReasoningRule, ...]:
        return self._sort([r for r in self._rules.values() if r.definition.status is ReasoningRuleStatus.ENABLED])

    def list_by_scope(self, scope: ReasoningRuleScope | str) -> tuple[ReasoningRule, ...]:
        try:
            target = scope if isinstance(scope, ReasoningRuleScope) else ReasoningRuleScope(scope)
        except (TypeError, ValueError) as exc:
            raise ReasoningRuleRegistryError("invalid scope", field="scope") from exc
        return self._sort([r for r in self._rules.values() if r.definition.scope is target])

    def list_by_domain(self, domain_id: str) -> tuple[ReasoningRule, ...]:
        return self._sort([r for r in self._rules.values() if r.definition.domain_id == domain_id])

    def list_by_category(
        self, category: ReasoningRuleCategory | str
    ) -> tuple[ReasoningRule, ...]:
        try:
            target = (
                category
                if isinstance(category, ReasoningRuleCategory)
                else ReasoningRuleCategory(category)
            )
        except (TypeError, ValueError) as exc:
            raise ReasoningRuleRegistryError(
                "invalid category", field="category"
            ) from exc
        return self._sort(
            [r for r in self._rules.values() if r.definition.category is target]
        )

    def list_by_status(
        self, status: ReasoningRuleStatus | str
    ) -> tuple[ReasoningRule, ...]:
        try:
            target = (
                status
                if isinstance(status, ReasoningRuleStatus)
                else ReasoningRuleStatus(status)
            )
        except (TypeError, ValueError) as exc:
            raise ReasoningRuleRegistryError("invalid status", field="status") from exc
        return self._sort(
            [r for r in self._rules.values() if r.definition.status is target]
        )

    def inspect_definitions(self) -> tuple[ReasoningRuleDefinition, ...]:
        return tuple(rule.definition for rule in self.list_all())

    # ── Snapshot / restore ───────────────────────────────────────────────────

    def snapshot_state(self) -> ReasoningRuleRegistrySnapshot:
        """Capture the full registry state for transactional rollback."""
        rules = tuple(
            sorted(
                self._rules.values(),
                key=lambda rule: (rule.definition.id, _semver_key(rule.definition.version)),
            )
        )
        return ReasoningRuleRegistrySnapshot(rules=rules)

    def restore_state(self, snapshot: ReasoningRuleRegistrySnapshot) -> None:
        """Restore the full registry state from a snapshot.

        Validates the snapshot completely before mutating.  Rejects wrong
        types and invalid snapshots without modifying the registry.
        """
        if not isinstance(snapshot, ReasoningRuleRegistrySnapshot):
            raise ReasoningRuleRegistryError(
                "snapshot must be a ReasoningRuleRegistrySnapshot",
                field="snapshot",
            )
        if not isinstance(snapshot.rules, tuple):
            raise ReasoningRuleRegistryError(
                "snapshot.rules must be a tuple",
                field="snapshot.rules",
            )
        for rule in snapshot.rules:
            _validate_rule(rule)

        # Reject duplicate (id, version) keys before reconstructing the dictionary
        keys = [(rule.definition.id, rule.definition.version) for rule in snapshot.rules]
        if len(keys) != len(set(keys)):
            raise ReasoningRuleRegistryError(
                "snapshot.rules contains duplicate (id, version) keys",
                field="snapshot.rules",
            )

        # All validation passed — mutate
        self._rules = {
            (rule.definition.id, rule.definition.version): rule
            for rule in snapshot.rules
        }


__all__ = [
    "InMemoryReasoningRuleRegistry",
    "ReasoningRuleRegistry",
    "ReasoningRuleRegistrySnapshot",
]
