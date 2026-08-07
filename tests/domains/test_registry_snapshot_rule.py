"""Tests for InMemoryReasoningRuleRegistry snapshot/restore support."""

from __future__ import annotations

import pytest

from cmm.cognitive.enums import (
    ReasoningRuleCategory,
    ReasoningRuleScope,
    ReasoningRuleStatus,
)
from cmm.cognitive.errors import ReasoningRuleRegistryError
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleDefinition
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry


class _Rule:
    def __init__(self, definition: ReasoningRuleDefinition):
        self.definition = definition

    def evaluate(self, context):
        return None


def _rule(rule_id: str, version: str = "1.0.0") -> _Rule:
    return _Rule(
        ReasoningRuleDefinition(
            id=f"test.{rule_id}",
            name=rule_id,
            version=version,
            scope=ReasoningRuleScope.GLOBAL,
            category=ReasoningRuleCategory.EPISTEMIC,
            status=ReasoningRuleStatus.ENABLED,
            priority=100,
            risk_level="low",
            deterministic=True,
            description="test rule",
            metadata={},
        )
    )


def test_snapshot_state_exists():
    """RED: snapshot_state() must exist."""
    registry = InMemoryReasoningRuleRegistry()
    assert hasattr(registry, "snapshot_state")


def test_restore_state_exists():
    """RED: restore_state() must exist."""
    registry = InMemoryReasoningRuleRegistry()
    assert hasattr(registry, "restore_state")


def test_round_trip_restores_exact_state():
    """Snapshot → mutate → restore → snapshot equals initial."""
    registry = InMemoryReasoningRuleRegistry()
    registry.register(_rule("rule1"))
    registry.register(_rule("rule2"))

    before = registry.snapshot_state()

    registry.register(_rule("rule3"))

    after_mutation = registry.snapshot_state()
    assert len(after_mutation.rules) == 3

    registry.restore_state(before)
    after_restore = registry.snapshot_state()

    assert after_restore.rules == before.rules
    assert len(after_restore.rules) == 2


def test_preexisting_entries_preserved():
    """Restore preserves pre-existing entries."""
    registry = InMemoryReasoningRuleRegistry()
    registry.register(_rule("rule1"))

    before = registry.snapshot_state()

    registry.register(_rule("rule2"))

    registry.restore_state(before)

    assert registry.get("test.rule1", "1.0.0") is not None
    assert registry.get("test.rule2", "1.0.0") is None


def test_empty_registry_round_trip():
    """Empty registry snapshot/restore works."""
    registry = InMemoryReasoningRuleRegistry()
    before = registry.snapshot_state()
    registry.restore_state(before)
    after = registry.snapshot_state()
    assert after.rules == before.rules
    assert after.rules == ()


def test_multiple_versions_restored():
    """Multiple versions of the same rule are restored."""
    registry = InMemoryReasoningRuleRegistry()
    registry.register(_rule("rule1", "1.0.0"))
    registry.register(_rule("rule1", "2.0.0"))

    before = registry.snapshot_state()
    assert len(before.rules) == 2

    registry.register(_rule("rule2", "1.0.0"))
    registry.restore_state(before)

    assert registry.get("test.rule1", "1.0.0") is not None
    assert registry.get("test.rule1", "2.0.0") is not None
    assert registry.get("test.rule2", "1.0.0") is None


def test_deterministic_order():
    """Snapshot rules are in deterministic order."""
    registry = InMemoryReasoningRuleRegistry()
    registry.register(_rule("b"))
    registry.register(_rule("a"))

    snap = registry.snapshot_state()
    ids = [r.definition.id for r in snap.rules]
    assert ids == sorted(ids)


def test_snapshot_deeply_immutable():
    """Snapshot is deeply immutable."""
    registry = InMemoryReasoningRuleRegistry()
    registry.register(_rule("rule1"))
    snap = registry.snapshot_state()

    with pytest.raises(AttributeError):
        snap.rules[0].definition.id = "changed"  # type: ignore[misc]


def test_wrong_type_rejected():
    """restore_state rejects wrong types."""
    registry = InMemoryReasoningRuleRegistry()
    with pytest.raises(ReasoningRuleRegistryError):
        registry.restore_state("not a snapshot")  # type: ignore[arg-type]


def test_invalid_snapshot_does_not_mutate():
    """Invalid snapshot does not modify the registry."""
    registry = InMemoryReasoningRuleRegistry()
    registry.register(_rule("rule1"))
    before = registry.snapshot_state()

    with pytest.raises(ReasoningRuleRegistryError):
        registry.restore_state(object())  # type: ignore[arg-type]

    after = registry.snapshot_state()
    assert after.rules == before.rules


def test_double_restore_idempotent():
    """Two consecutive restores are idempotent."""
    registry = InMemoryReasoningRuleRegistry()
    registry.register(_rule("rule1"))
    before = registry.snapshot_state()

    registry.register(_rule("rule2"))
    registry.restore_state(before)
    registry.restore_state(before)

    after = registry.snapshot_state()
    assert after.rules == before.rules
def test_duplicate_rule_id_version_rejected():
    """A well-typed snapshot with duplicate (rule id, version) keys is rejected without mutation."""
    from cmm.cognitive.reasoning_rule_registry import ReasoningRuleRegistrySnapshot

    registry = InMemoryReasoningRuleRegistry()
    registry.register(_rule("rule1"))
    before = registry.snapshot_state()

    duplicate = ReasoningRuleRegistrySnapshot(
        rules=(_rule("rule1"), _rule("rule1")),
    )
    with pytest.raises(ReasoningRuleRegistryError):
        registry.restore_state(duplicate)

    after = registry.snapshot_state()
    assert after.rules == before.rules


class _RuleExtraRequired:
    def __init__(self, definition: ReasoningRuleDefinition):
        self.definition = definition

    def evaluate(self, context, required_extra):
        return None


class _RuleVarargs:
    def __init__(self, definition: ReasoningRuleDefinition):
        self.definition = definition

    def evaluate(self, context, *args):
        return None


class _RuleOptionalExtra:
    def __init__(self, definition: ReasoningRuleDefinition):
        self.definition = definition

    def evaluate(self, context, extra=None):
        return None


def test_snapshot_rejects_rule_rejected_by_register_without_mutation():
    """A well-typed rule whose evaluate signature register() rejects must also
    be rejected by restore_state(), before any mutation."""
    from cmm.cognitive.reasoning_rule_registry import ReasoningRuleRegistrySnapshot

    invalid = _RuleExtraRequired(_rule("rule_bad").definition)

    # register() rejects it (second required positional).
    fresh_registry = InMemoryReasoningRuleRegistry()
    with pytest.raises(ReasoningRuleRegistryError):
        fresh_registry.register(invalid)

    # A structurally valid snapshot carrying the same rule.
    snapshot = ReasoningRuleRegistrySnapshot(rules=(invalid,))

    registry = InMemoryReasoningRuleRegistry()
    registry.register(_rule("rule1"))
    before = registry.snapshot_state()

    with pytest.raises(ReasoningRuleRegistryError):
        registry.restore_state(snapshot)

    after = registry.snapshot_state()
    assert after.rules == before.rules


def test_snapshot_rejects_varargs_rule_without_mutation():
    """A rule whose evaluate accepts *args is rejected by register() and must
    also be rejected by restore_state() without mutation."""
    from cmm.cognitive.reasoning_rule_registry import ReasoningRuleRegistrySnapshot

    invalid = _RuleVarargs(_rule("rule_varargs").definition)

    fresh_registry = InMemoryReasoningRuleRegistry()
    with pytest.raises(ReasoningRuleRegistryError):
        fresh_registry.register(invalid)

    snapshot = ReasoningRuleRegistrySnapshot(rules=(invalid,))

    registry = InMemoryReasoningRuleRegistry()
    registry.register(_rule("rule1"))
    before = registry.snapshot_state()

    with pytest.raises(ReasoningRuleRegistryError):
        registry.restore_state(snapshot)

    after = registry.snapshot_state()
    assert after.rules == before.rules


def test_valid_reasoning_rule_snapshot_still_restores():
    """A rule register() accepts (including an optional extra parameter) must
    still be restorable."""
    registry = InMemoryReasoningRuleRegistry()
    registry.register(_RuleOptionalExtra(_rule("rule_optional").definition))
    before = registry.snapshot_state()

    registry.restore_state(before)

    after = registry.snapshot_state()
    assert after.rules == before.rules
