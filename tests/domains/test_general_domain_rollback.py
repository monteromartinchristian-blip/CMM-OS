"""Tests for General Domain atomic rollback after post-mutation failures."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.cognitive.reasoning_rule_registry import InMemoryReasoningRuleRegistry
from cmm.domains.general import (
    GENERAL_DOMAIN_ID,
    build_general_operation_definitions,
    register_general_domain,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.profile_registry import InMemoryDomainProfileRegistry
from cmm.domains.registry import DomainRegistry
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry


class _FakeImplementation:
    def __init__(self, definition):
        self.definition = definition

    def execute(self, request):
        return {"success": True, "output": {}, "effects": ()}


class _FailAfterN:
    """Wrapper that allows N successful registrations, then raises."""

    def __init__(self, inner, fail_after: int):
        self._inner = inner
        self._fail_after = fail_after
        self._count = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def register(self, *args, **kwargs):
        if self._count >= self._fail_after:
            raise RuntimeError("simulated post-mutation failure")
        self._count += 1
        return self._inner.register(*args, **kwargs)


def _registries():
    return {
        "domain_registry": DomainRegistry(),
        "profile_registry": InMemoryDomainProfileRegistry(),
        "resource_registry": InMemoryDomainResourceRegistry(),
        "rule_registry": InMemoryReasoningRuleRegistry(),
        "operation_registry": InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        "workflow_registry": InMemoryDomainWorkflowRegistry(
            InMemoryWorkflowRegistry()
        ),
        "permission_registry": DomainPermissionRegistry(),
    }


def _implementations():
    return {
        op.operation_id: _FakeImplementation(op)
        for op in build_general_operation_definitions()
    }


def _snapshot_all(registries):
    """Capture snapshots of all registries."""
    return {
        name: registry.snapshot_state()
        for name, registry in registries.items()
    }


def _assert_snapshots_equal(a, b):
    """Assert two snapshot dicts are equal."""
    assert set(a.keys()) == set(b.keys())
    for key in a:
        assert a[key] == b[key], f"snapshot mismatch for {key}"


def _assert_no_general_entries(registries):
    """Assert no General Domain entries remain in any registry."""
    assert registries["domain_registry"].get(GENERAL_DOMAIN_ID) is None
    assert registries["profile_registry"].get("general.profile") is None
    assert registries["resource_registry"].list_all() == ()
    assert registries["rule_registry"].list_all() == ()
    assert registries["operation_registry"].list_definitions() == ()
    assert registries["workflow_registry"].list_for_domain(GENERAL_DOMAIN_ID) == ()


def test_failure_after_definition_rolls_back():
    """Failure after domain definition registration rolls back all registries."""
    registries = _registries()
    registries["domain_registry"] = _FailAfterN(registries["domain_registry"], fail_after=0)

    before = _snapshot_all(registries)

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_general_domain(
            **registries,
            operation_implementations=_implementations(),
        )

    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_general_entries(registries)


def test_failure_during_resources_rolls_back():
    """Failure during resource registration rolls back all registries."""
    registries = _registries()
    # Allow domain + profile to register, fail on first resource
    registries["resource_registry"] = _FailAfterN(registries["resource_registry"], fail_after=0)

    before = _snapshot_all(registries)

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_general_domain(
            **registries,
            operation_implementations=_implementations(),
        )

    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_general_entries(registries)


def test_failure_after_profile_rolls_back():
    """Failure after profile registration rolls back all registries."""
    registries = _registries()
    # Allow domain + profile to register, fail on first resource
    registries["resource_registry"] = _FailAfterN(registries["resource_registry"], fail_after=0)

    before = _snapshot_all(registries)

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_general_domain(
            **registries,
            operation_implementations=_implementations(),
        )

    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_general_entries(registries)


def test_failure_during_rules_rolls_back():
    """Failure during rule registration rolls back all registries."""
    registries = _registries()
    # Allow domain + profile + 9 resources, fail on first rule
    registries["rule_registry"] = _FailAfterN(registries["rule_registry"], fail_after=0)

    before = _snapshot_all(registries)

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_general_domain(
            **registries,
            operation_implementations=_implementations(),
        )

    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_general_entries(registries)


def test_failure_during_operations_rolls_back():
    """Failure during operation registration rolls back all registries."""
    registries = _registries()
    # Allow domain + profile + resources + rules, fail on first operation
    registries["operation_registry"] = _FailAfterN(
        registries["operation_registry"], fail_after=0
    )

    before = _snapshot_all(registries)

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_general_domain(
            **registries,
            operation_implementations=_implementations(),
        )

    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_general_entries(registries)


def test_failure_during_workflows_rolls_back():
    """Failure during workflow registration rolls back all registries."""
    registries = _registries()
    # Allow domain + profile + resources + rules + operations, fail on first workflow
    registries["workflow_registry"] = _FailAfterN(
        registries["workflow_registry"], fail_after=0
    )

    before = _snapshot_all(registries)

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_general_domain(
            **registries,
            operation_implementations=_implementations(),
        )

    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_general_entries(registries)


def test_failure_during_permission_rolls_back():
    """Failure during permission policy registration rolls back all registries."""
    registries = _registries()
    # Allow everything except permission, fail on permission
    registries["permission_registry"] = _FailAfterN(
        registries["permission_registry"], fail_after=0
    )

    before = _snapshot_all(registries)

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_general_domain(
            **registries,
            operation_implementations=_implementations(),
        )

    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)
    _assert_no_general_entries(registries)


def test_preexisting_entries_preserved_after_rollback():
    """Pre-existing entries survive rollback."""
    registries = _registries()

    # Pre-register an unrelated resource
    from cmm.cognitive.enums import SensitivityLevel
    from cmm.domains.resource_contracts import (
        DomainResourceDefinition,
        DomainResourceTemporalPolicy,
    )

    unrelated = DomainResourceDefinition(
        id="unrelated.resource",
        kind="unrelated",
        domain_id="domain:unrelated",
        adapter="cognitive.unrelated",
        entity_types=("unrelated",),
        default_sensitivity=SensitivityLevel.INTERNAL,
        default_reliability=0.5,
        temporal_policy=DomainResourceTemporalPolicy(
            effective_date_required=False,
            expiration_required=False,
            historical_allowed=True,
        ),
        metadata={"phase": "test"},
    )
    registries["resource_registry"].register(unrelated)

    # Fail on first resource registration
    registries["resource_registry"] = _FailAfterN(
        registries["resource_registry"], fail_after=0
    )

    before = _snapshot_all(registries)

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_general_domain(
            **registries,
            operation_implementations=_implementations(),
        )

    after = _snapshot_all(registries)
    _assert_snapshots_equal(before, after)

    # Unrelated resource must still exist
    assert registries["resource_registry"].get("unrelated.resource") is not None


def test_retry_succeeds_after_rollback():
    """Retry succeeds after a rollback."""
    registries = _registries()

    # Fail on first resource registration
    registries["resource_registry"] = _FailAfterN(
        registries["resource_registry"], fail_after=0
    )

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_general_domain(
            **registries,
            operation_implementations=_implementations(),
        )

    # Replace with working registry and retry
    registries["resource_registry"] = InMemoryDomainResourceRegistry()

    result = register_general_domain(
        **registries,
        operation_implementations=_implementations(),
    )
    assert result.definition.id.slug == "general"
    assert registries["domain_registry"].get(GENERAL_DOMAIN_ID) is not None
    assert len(registries["resource_registry"].list_all()) == 9


def test_rollback_is_deterministic():
    """The same failure reproduces deterministically with same rollback."""
    registries = _registries()
    registries["resource_registry"] = _FailAfterN(
        registries["resource_registry"], fail_after=0
    )

    before = _snapshot_all(registries)

    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_general_domain(
            **registries,
            operation_implementations=_implementations(),
        )

    after_first = _snapshot_all(registries)
    _assert_snapshots_equal(before, after_first)

    # Second attempt produces the same result
    with pytest.raises(RuntimeError, match="simulated post-mutation failure"):
        register_general_domain(
            **registries,
            operation_implementations=_implementations(),
        )

    after_second = _snapshot_all(registries)
    _assert_snapshots_equal(before, after_second)
